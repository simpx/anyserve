use pyo3::prelude::*;
use std::fs;
use std::path::PathBuf;
use uuid::Uuid;
use std::io::Write;
use tonic::{transport::Server, Request, Response, Status};

pub mod pb {
    tonic::include_proto!("anyserve");
}

use pb::agent_service_server::{AgentService, AgentServiceServer};
use pb::{GetObjectRequest, GetObjectResponse};

// --- gRPC Service Implementation ---

#[derive(Debug)]
struct AgentServiceImpl {
    root_dir: PathBuf,
    instance_id: String,
}

#[tonic::async_trait]
impl AgentService for AgentServiceImpl {
    async fn get_object(
        &self,
        request: Request<GetObjectRequest>,
    ) -> Result<Response<GetObjectResponse>, Status> {
        let req = request.into_inner();
        let path = self
            .root_dir
            .join("instances")
            .join(&self.instance_id) // Read from MY local storage
            .join("objects")
            .join(&req.uuid);

        if path.exists() {
            let data = fs::read(path).map_err(|e| Status::internal(e.to_string()))?;
            Ok(Response::new(GetObjectResponse {
                data,
                found: true,
            }))
        } else {
            Ok(Response::new(GetObjectResponse {
                data: vec![],
                found: false,
            }))
        }
    }
}

// --- Python Integration ---

#[pyclass]
struct AnyserveCore {
    root_dir: PathBuf,
    instance_id: String,
    port: u16,
    http_port: u16,
}

#[pymethods]
impl AnyserveCore {
    #[new]
    fn new(root_dir: String, instance_id: String, port: u16, http_port: u16) -> PyResult<Self> {
        let root = PathBuf::from(&root_dir);
        let instance_path = root.join("instances").join(&instance_id).join("objects");
        let names_path = root.join("names");

        fs::create_dir_all(&instance_path)?;
        fs::create_dir_all(&names_path)?;

        let core = AnyserveCore {
            root_dir: root.clone(),
            instance_id: instance_id.clone(),
            port,
            http_port,
        };

        // Start gRPC server in background
        core.start_server_thread();

        Ok(core)
    }

    fn put_object(&self, data: Vec<u8>) -> PyResult<String> {
        // Same as before: Local Write
        let id = Uuid::new_v4();
        let path = self
            .root_dir
            .join("instances")
            .join(&self.instance_id)
            .join("objects")
            .join(id.to_string());
        
        let mut file = fs::File::create(path)?;
        file.write_all(&data)?;
        
        Ok(id.to_string())
    }

    fn get_object_network(&self, object_id: String, owner_address: String) -> PyResult<Vec<u8>> {
        // Network Read via gRPC
        // Note: owner_address should be "ip:port"
        
        // Handle "localhost" case for PoC: if address has no port, assume logic or error?
        // Let's assume owner_address is "127.0.0.1:port"

        let rt = tokio::runtime::Runtime::new().unwrap();
        rt.block_on(async {
            // Must add http:// scheme for tonic
            let endpoint = format!("http://{}", owner_address);
            let mut client = pb::agent_service_client::AgentServiceClient::connect(endpoint)
                .await
                .map_err(|e| pyo3::exceptions::PyConnectionError::new_err(e.to_string()))?;

            let request = tonic::Request::new(GetObjectRequest { uuid: object_id });
            let response = client.get_object(request).await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
            
            let resp_inner = response.into_inner();
            if resp_inner.found {
                Ok(resp_inner.data)
            } else {
                Err(pyo3::exceptions::PyKeyError::new_err("Object not found on remote"))
            }
        })
    }

    fn register_service(&self, service_name: String) -> PyResult<()> {
        let service_dir = self.root_dir.join("names").join(&service_name);
        fs::create_dir_all(&service_dir)?;
        
        let instance_file = service_dir.join(&self.instance_id);
        // Use HTTP port for Service Registry (Control Plane)
        let address = format!("127.0.0.1:{}", self.http_port);
        let mut file = fs::File::create(instance_file)?;
        file.write_all(address.as_bytes())?;
        
        Ok(())
    }

    fn lookup_service(&self, service_name: String) -> PyResult<Vec<String>> {
        // Returns list of addresses
        let service_dir = self.root_dir.join("names").join(&service_name);
        let mut instances = Vec::new();

        if service_dir.exists() {
            for entry in fs::read_dir(service_dir)? {
                let entry = entry?;
                let file_name = entry.file_name();
                if let Some(_name) = file_name.to_str() {
                    // Read content for address
                    let addr = fs::read_to_string(entry.path()).unwrap_or_default();
                    instances.push(addr);
                }
            }
        }
        Ok(instances)
    }
    
    fn get_instance_id(&self) -> String {
        self.instance_id.clone()
    }

    fn get_address(&self) -> String {
        format!("127.0.0.1:{}", self.port)
    }
}

impl AnyserveCore {
    fn start_server_thread(&self) {
        let addr_str = format!("0.0.0.0:{}", self.port);
        let root = self.root_dir.clone();
        let iid = self.instance_id.clone();
        
        std::thread::spawn(move || {
            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                let addr = addr_str.parse().unwrap();
                let service = AgentServiceImpl {
                    root_dir: root,
                    instance_id: iid,
                };
                
                println!("[Rust] gRPC Server listening on {}", addr);
                
                Server::builder()
                    .add_service(AgentServiceServer::new(service))
                    .serve(addr)
                    .await
                    .unwrap();
            });
        });
    }
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<AnyserveCore>()?;
    Ok(())
}
