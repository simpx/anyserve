// use std::env;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use shared_memory::ShmemConf;
use tokio::net::UnixStream;
use tokio::io::{AsyncReadExt};
use tonic::{transport::{Endpoint, Server, Uri}, Request, Response, Status};
use tower::service_fn;
use hyper_util::rt::tokio::TokioIo;
use std::process::Stdio;
use std::os::unix::io::FromRawFd;

pub mod pb {
    tonic::include_proto!("inference");
}

use pb::grpc_inference_service_server::{GrpcInferenceService, GrpcInferenceServiceServer};
use pb::{ModelInferRequest, ModelInferResponse};

const SHM_SIZE: usize = 100 * 1024 * 1024; // 100MB
const UDS_PATH: &str = "/tmp/anyserve_demo.sock";
const SHM_LINK: &str = "/tmp/anyserve_demo_shm";

struct ShmManager {
    shm: shared_memory::Shmem,
    offset: usize,
}

// Safety: We use a Mutex to access this, and the raw pointer is to a valid SHM region.
unsafe impl Send for ShmManager {}
unsafe impl Sync for ShmManager {}

impl ShmManager {
    fn new() -> Self {
        let shm = ShmemConf::new()
            .size(SHM_SIZE)
            .flink(SHM_LINK)
            .create()
            .expect("Failed to create SHM");
        ShmManager { shm, offset: 0 }
    }

    fn write(&mut self, data: &[u8]) -> (usize, usize) {
        let len = data.len();
        if self.offset + len > SHM_SIZE {
            // Simple ring buffer reset for MVP
            self.offset = 0;
        }
        let start = self.offset;
        unsafe {
            let ptr = self.shm.as_ptr().add(start);
            std::ptr::copy_nonoverlapping(data.as_ptr(), ptr, len);
        }
        self.offset += len;
        (start, len)
    }
}

struct ProxyService {
    shm: Arc<Mutex<ShmManager>>,
    client: pb::grpc_inference_service_client::GrpcInferenceServiceClient<tonic::transport::Channel>,
}

impl ProxyService {
    async fn connect_worker() -> Result<pb::grpc_inference_service_client::GrpcInferenceServiceClient<tonic::transport::Channel>, Box<dyn std::error::Error>> {
        let channel = Endpoint::try_from("http://[::]:50051")?
            .connect_with_connector(service_fn(|_: Uri| async {
                let stream = UnixStream::connect(UDS_PATH).await?;
                Ok::<_, std::io::Error>(TokioIo::new(stream))
            }))
            .await?;
        Ok(pb::grpc_inference_service_client::GrpcInferenceServiceClient::new(channel))
    }
}

#[tonic::async_trait]
impl GrpcInferenceService for ProxyService {
    // Boilerplate for other methods
    async fn server_live(&self, _req: Request<pb::ServerLiveRequest>) -> Result<Response<pb::ServerLiveResponse>, Status> {
        Ok(Response::new(pb::ServerLiveResponse { live: true }))
    }
    async fn server_ready(&self, _req: Request<pb::ServerReadyRequest>) -> Result<Response<pb::ServerReadyResponse>, Status> {
        Ok(Response::new(pb::ServerReadyResponse { ready: true }))
    }
    async fn model_ready(&self, _req: Request<pb::ModelReadyRequest>) -> Result<Response<pb::ModelReadyResponse>, Status> {
        Ok(Response::new(pb::ModelReadyResponse { ready: true }))
    }
    async fn server_metadata(&self, _req: Request<pb::ServerMetadataRequest>) -> Result<Response<pb::ServerMetadataResponse>, Status> {
        Ok(Response::new(pb::ServerMetadataResponse::default()))
    }
    async fn model_metadata(&self, _req: Request<pb::ModelMetadataRequest>) -> Result<Response<pb::ModelMetadataResponse>, Status> {
        Ok(Response::new(pb::ModelMetadataResponse::default()))
    }

    // Capture logic
    async fn model_infer(&self, request: Request<ModelInferRequest>) -> Result<Response<ModelInferResponse>, Status> {
        let mut req = request.into_inner();

        // 1. Move heavy data to SHM
        if !req.raw_input_contents.is_empty() {
             let mut shm = self.shm.lock().unwrap();
             // Just take the first one for MVP demo
             if let Some(data) = req.raw_input_contents.first() {
                 let (offset, len) = shm.write(data);
                 println!("Moved {} bytes to SHM at offset {}", len, offset);
                 
                 // 2. Inject Metadata
                 // We find the first input and add parameters
                 if let Some(input) = req.inputs.first_mut() {
                     let params = &mut input.parameters;
                     
                     // Use top-level InferParameter
                     params.insert("__shm_offset__".to_string(), pb::InferParameter {
                         parameter_choice: Some(pb::infer_parameter::ParameterChoice::Int64Param(offset as i64))
                     });
                     params.insert("__shm_len__".to_string(), pb::InferParameter {
                         parameter_choice: Some(pb::infer_parameter::ParameterChoice::Int64Param(len as i64))
                     });
                 }
                 
                 // 3. Clear body
                 req.raw_input_contents.clear();
             }
        }

        // 4. Forward to Python via UDS
        let mut client = self.client.clone();
        let response = client.model_infer(req).await?;
        Ok(response)
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let _ = std::fs::remove_file(SHM_LINK); // Clean up old link

    println!("Starting Rust Proxy...");
    
    // Create a pipe for readiness notification
    let mut fds: [i32; 2] = [0; 2];
    unsafe {
        // pipe() returns 2 file descriptors. 0 is read end, 1 is write end.
        if libc::pipe(fds.as_mut_ptr()) < 0 {
            return Err("Failed to create pipe".into());
        }
    }
    let read_fd = fds[0];
    let write_fd = fds[1];

    // Spawn Python Worker
    println!("Spawning Python worker with Notify FD: {}", write_fd);
    let worker_path = "worker/worker.py";
    
    let mut child = tokio::process::Command::new("uv")
        .args(&["run", "python", worker_path])
        .env("ANSERVE_READY_FD", write_fd.to_string())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("Failed to spawn python worker");

    // Close the write end in the parent process!
    // This is crucial. Only the child should hold the write end now.
    unsafe { libc::close(write_fd); }

    // Wait for worker readiness signal (read from pipe)
    println!("Waiting for worker signal...");
    
    // We convert the raw FD to a Tokio AsyncFd or File
    let mut pipe_reader = unsafe { tokio::fs::File::from_raw_fd(read_fd) };
    let mut buf = [0u8; 16];
    
    // When the child writes and closes (or just writes), we get data.
    // Use timeout to avoid hanging
    match tokio::time::timeout(Duration::from_secs(10), pipe_reader.read(&mut buf)).await {
        Ok(Ok(n)) if n > 0 => {
             let signal = String::from_utf8_lossy(&buf[..n]);
             if signal.contains("READY") {
                 println!("Worker signaled readiness: {}", signal);
             } else {
                 println!("Worker wrote unexpected data: {}", signal);
             }
        },
        Ok(Ok(_)) => {
            // EOF (0 bytes) -> Worker closed pipe without writing? Or crashed.
             child.kill().await?;
             return Err("Worker closed pipe without signaling ready".into());
        },
        Ok(Err(e)) => {
             child.kill().await?;
             return Err(format!("Failed to read from pipe: {}", e).into());
        },
        Err(_) => {
            child.kill().await?;
            return Err("Timed out waiting for worker readiness".into());
        }
    }

    // Connect to Worker
    let client_res = ProxyService::connect_worker().await;
    if let Err(e) = client_res {
        println!("Failed to connect to worker: {}", e);
        child.kill().await?;
        return Err(e);
    }
    let client = client_res.unwrap();
    println!("Connected to Python Worker via UDS");

    let service = ProxyService {
        shm: Arc::new(Mutex::new(ShmManager::new())),
        client,
    };

    let addr = "0.0.0.0:50055".parse()?;
    println!("Listening on {}", addr);

    Server::builder()
        .add_service(GrpcInferenceServiceServer::new(service))
        .serve(addr)
        .await?;
        
    child.kill().await?;

    Ok(())
}
