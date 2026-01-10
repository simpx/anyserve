//! anyServe Node - Rust Runtime (Control Plane)
//!
//! This is the main entry point for an anyServe node.
//! Each node:
//! - Starts a gRPC server for the AnyServe.Infer RPC
//! - Spawns a Python worker subprocess for execution
//! - Communicates with the Scheduler for delegation routing

use std::env;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tonic::{transport::Server, Request, Response, Status};

pub mod pb {
    tonic::include_proto!("anyserve");
}

use pb::any_serve_server::{AnyServe, AnyServeServer};
use pb::{InferRequest, InferResponse};

/// Worker request sent to Python via JSON
#[derive(Serialize)]
struct WorkerRequest {
    op: String,
    capability: String,
    inputs: String,
    input_refs: Vec<String>,
}

/// Worker response received from Python via JSON
#[derive(Deserialize)]
struct WorkerResponse {
    output: String,
    output_refs: Vec<String>,
    error: Option<String>,
}

/// Scheduler lookup response
#[derive(Deserialize)]
struct SchedulerLookupResponse {
    endpoints: Vec<String>,
}

/// The AnyServe gRPC service implementation
struct AnyServeImpl {
    node_id: String,
    capabilities: Vec<String>,
    scheduler_url: String,
    worker: Mutex<PythonWorker>,
}

struct PythonWorker {
    process: Child,
}

impl PythonWorker {
    fn new() -> Result<Self, std::io::Error> {
        let python_path = env::var("PYTHON_PATH").unwrap_or_else(|_| "python".to_string());
        let process = Command::new(&python_path)
            .args(["-m", "anyserve_worker"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;
        
        println!("[Node] Python worker started with PID: {}", process.id());
        Ok(PythonWorker { process })
    }

    fn call(&mut self, request: &WorkerRequest) -> Result<WorkerResponse, String> {
        let stdin = self.process.stdin.as_mut()
            .ok_or("Failed to get stdin")?;
        let stdout = self.process.stdout.as_mut()
            .ok_or("Failed to get stdout")?;

        // Send request as JSON line
        let json = serde_json::to_string(request)
            .map_err(|e| format!("JSON serialize error: {}", e))?;
        writeln!(stdin, "{}", json)
            .map_err(|e| format!("Write to worker failed: {}", e))?;
        stdin.flush()
            .map_err(|e| format!("Flush failed: {}", e))?;

        // Read response as JSON line
        let mut reader = BufReader::new(stdout);
        let mut line = String::new();
        reader.read_line(&mut line)
            .map_err(|e| format!("Read from worker failed: {}", e))?;

        let response: WorkerResponse = serde_json::from_str(&line)
            .map_err(|e| format!("JSON parse error: {}", e))?;

        Ok(response)
    }
}

impl AnyServeImpl {
    fn new(node_id: String, capabilities: Vec<String>, scheduler_url: String) -> Result<Self, String> {
        let worker = PythonWorker::new()
            .map_err(|e| format!("Failed to start worker: {}", e))?;
        
        Ok(AnyServeImpl {
            node_id,
            capabilities,
            scheduler_url,
            worker: Mutex::new(worker),
        })
    }

    fn lookup_capability(&self, capability: &str) -> Result<Vec<String>, String> {
        // Use a separate thread for blocking HTTP to avoid runtime conflicts
        let url = format!("{}/lookup?cap={}", self.scheduler_url, capability);
        
        let handle = std::thread::spawn(move || {
            let client = reqwest::blocking::Client::new();
            client.get(&url)
                .send()
                .map_err(|e| format!("Scheduler lookup failed: {}", e))?
                .json::<SchedulerLookupResponse>()
                .map_err(|e| format!("Parse lookup response failed: {}", e))
        });
        
        handle.join().unwrap()
            .map(|r| r.endpoints)
    }

    fn can_handle_locally(&self, capability: &str) -> bool {
        self.capabilities.contains(&capability.to_string())
    }

    async fn delegate(&self, target: &str, request: &InferRequest) -> Result<InferResponse, String> {
        println!("[Node] Delegating to {}", target);
        
        let endpoint = format!("http://{}", target);
        let mut client = pb::any_serve_client::AnyServeClient::connect(endpoint)
            .await
            .map_err(|e| format!("Failed to connect to delegate target: {}", e))?;

        let response = client.infer(tonic::Request::new(request.clone()))
            .await
            .map_err(|e| format!("Delegation call failed: {}", e))?;

        let mut resp = response.into_inner();
        resp.delegated = true;  // Mark as delegated
        Ok(resp)
    }
}

/// Register with scheduler (called before async runtime starts)
fn register_with_scheduler(scheduler_url: &str, node_id: &str, port: u16, capabilities: &[String]) -> Result<(), String> {
    let client = reqwest::blocking::Client::new();
    let endpoint = format!("127.0.0.1:{}", port);
    
    let body = serde_json::json!({
        "node_id": node_id,
        "endpoint": endpoint,
        "capabilities": capabilities
    });

    let url = format!("{}/register", scheduler_url);
    client.post(&url)
        .json(&body)
        .send()
        .map_err(|e| format!("Failed to register with scheduler: {}", e))?;
    
    println!("[Node] Registered with scheduler: {} -> {:?}", endpoint, capabilities);
    Ok(())
}

#[tonic::async_trait]
impl AnyServe for AnyServeImpl {
    async fn infer(
        &self,
        request: Request<InferRequest>,
    ) -> Result<Response<InferResponse>, Status> {
        let req = request.into_inner();
        println!("[Node {}] Received infer request: capability={}", self.node_id, req.capability);

        // Check if we can handle locally
        if self.can_handle_locally(&req.capability) {
            println!("[Node {}] Handling locally", self.node_id);
            
            // Call Python worker
            let worker_req = WorkerRequest {
                op: "infer".to_string(),
                capability: req.capability.clone(),
                inputs: String::from_utf8_lossy(&req.inputs).to_string(),
                input_refs: req.input_refs.clone(),
            };

            let mut worker = self.worker.lock().unwrap();
            match worker.call(&worker_req) {
                Ok(resp) => {
                    if let Some(err) = resp.error {
                        return Err(Status::internal(err));
                    }
                    Ok(Response::new(InferResponse {
                        output: resp.output.into_bytes(),
                        output_refs: resp.output_refs,
                        delegated: false,
                    }))
                }
                Err(e) => Err(Status::internal(e)),
            }
        } else {
            println!("[Node {}] Cannot handle '{}' locally, looking up delegation target", self.node_id, req.capability);
            
            // Lookup delegation target from scheduler
            match self.lookup_capability(&req.capability) {
                Ok(endpoints) if !endpoints.is_empty() => {
                    let target = &endpoints[0];
                    match self.delegate(target, &req).await {
                        Ok(resp) => Ok(Response::new(resp)),
                        Err(e) => Err(Status::internal(e)),
                    }
                }
                Ok(_) => Err(Status::not_found(format!("No node found for capability: {}", req.capability))),
                Err(e) => Err(Status::internal(e)),
            }
        }
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Parse command line arguments
    let args: Vec<String> = env::args().collect();
    
    let node_id = args.get(1)
        .cloned()
        .unwrap_or_else(|| "node-a".to_string());
    
    let port: u16 = args.get(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(50051);
    
    let capabilities: Vec<String> = args.get(3)
        .map(|s| s.split(',').map(|c| c.trim().to_string()).collect())
        .unwrap_or_else(|| vec!["small".to_string()]);
    
    let scheduler_url = args.get(4)
        .cloned()
        .unwrap_or_else(|| "http://127.0.0.1:8000".to_string());

    println!("=================================================");
    println!("[Node {}] Starting on port {}", node_id, port);
    println!("[Node {}] Capabilities: {:?}", node_id, capabilities);
    println!("[Node {}] Scheduler: {}", node_id, scheduler_url);
    println!("=================================================");

    // Register with scheduler BEFORE starting async runtime
    register_with_scheduler(&scheduler_url, &node_id, port, &capabilities)?;

    // Create the service
    let service = AnyServeImpl::new(node_id.clone(), capabilities, scheduler_url)
        .map_err(|e| format!("Failed to create service: {}", e))?;

    // Start the async runtime
    let rt = tokio::runtime::Runtime::new()?;
    rt.block_on(async {
        let addr = format!("0.0.0.0:{}", port).parse()?;
        println!("[Node {}] gRPC server listening on {}", node_id, addr);

        Server::builder()
            .add_service(AnyServeServer::new(service))
            .serve(addr)
            .await?;

        Ok::<(), Box<dyn std::error::Error>>(())
    })?;

    Ok(())
}
