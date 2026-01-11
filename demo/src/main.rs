// use std::env;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::net::UnixStream;
use tokio::io::{AsyncReadExt};
use tonic::{transport::{Endpoint, Server, Uri}, Request, Response, Status};
use tower::service_fn;
use hyper_util::rt::tokio::TokioIo;
use std::process::Stdio;
use std::os::unix::io::FromRawFd;
use uuid::Uuid;
use std::ffi::CString;
use std::ptr;

pub mod pb {
    tonic::include_proto!("inference");
}

use pb::grpc_inference_service_server::{GrpcInferenceService, GrpcInferenceServiceServer};
use pb::{ModelInferRequest, ModelInferResponse};

const SHM_SIZE: usize = 100 * 1024 * 1024; // 100MB
const UDS_PATH: &str = "/tmp/anyserve_demo.sock";

// Wrapper for Raw POSIX Shared Memory
struct RawShm {
    fd: i32,
    ptr: *mut u8,
    size: usize,
}

unsafe impl Send for RawShm {}
unsafe impl Sync for RawShm {}

impl RawShm {
    fn new(size: usize) -> Result<Self, String> {
        unsafe {
            // Use short name for macOS compatibility (PSHM_NAME_LEN=31)
            // /as_ + 8 chars = 12 chars
            let uuid_simple = Uuid::new_v4().simple().to_string();
            let name_str = format!("/as_{}", &uuid_simple[0..8]);
            let name = CString::new(name_str).unwrap();

            // 1. Create shm (O_CREAT | O_RDWR | O_EXCL)
            let fd = libc::shm_open(name.as_ptr(), libc::O_CREAT | libc::O_RDWR | libc::O_EXCL, 0o600);
            if fd < 0 {
                let err = std::io::Error::last_os_error();
                return Err(format!("shm_open failed: {}", err));
            }

            // 2. Unlink immediately (Anonymous behavior)
            // The name is removed, but the inode persists as long as FD is open
            libc::shm_unlink(name.as_ptr());

            // 2b. Clear FD_CLOEXEC because shm_open sets it by default
            // We need the child process to inherit this FD
            let flags = libc::fcntl(fd, libc::F_GETFD);
            if flags >= 0 {
                libc::fcntl(fd, libc::F_SETFD, flags & !libc::FD_CLOEXEC);
            }

            // 3. Resize
            if libc::ftruncate(fd, size as i64) < 0 {
                libc::close(fd);
                return Err("ftruncate failed".to_string());
            }

            // 4. Map
            let ptr = libc::mmap(
                ptr::null_mut(),
                size,
                libc::PROT_READ | libc::PROT_WRITE,
                libc::MAP_SHARED,
                fd,
                0
            );

            if ptr == libc::MAP_FAILED {
                libc::close(fd);
                return Err("mmap failed".to_string());
            }

            Ok(RawShm { fd, ptr: ptr as *mut u8, size })
        }
    }
}

impl Drop for RawShm {
    fn drop(&mut self) {
        unsafe {
            libc::munmap(self.ptr as *mut _, self.size);
            libc::close(self.fd);
        }
    }
}

struct ShmManager {
    shm_h2d: RawShm,
    h2d_offset: usize,
    shm_d2h: RawShm,
}

// Safety: We use a Mutex to access this, and the raw pointer is to a valid SHM region.
unsafe impl Send for ShmManager {}
unsafe impl Sync for ShmManager {}

impl ShmManager {
    fn new() -> Self {
        let shm_h2d = RawShm::new(SHM_SIZE).expect("Failed to create H2D SHM");
        let shm_d2h = RawShm::new(SHM_SIZE).expect("Failed to create D2H SHM");

        ShmManager { 
            shm_h2d, 
            h2d_offset: 0,
            shm_d2h,
        }
    }

    // Write to H2D buffer
    fn write_h2d(&mut self, data: &[u8]) -> (usize, usize) {
        let len = data.len();
        if self.h2d_offset + len > SHM_SIZE {
            self.h2d_offset = 0;
        }
        let start = self.h2d_offset;
        unsafe {
            let ptr = self.shm_h2d.ptr.add(start);
            std::ptr::copy_nonoverlapping(data.as_ptr(), ptr, len);
        }
        self.h2d_offset += len;
        (start, len)
    }

    // Read from D2H buffer
    fn read_d2h(&self, offset: usize, len: usize) -> Vec<u8> {
        let mut buf = vec![0u8; len];
        unsafe {
             let ptr = self.shm_d2h.ptr.add(offset);
             std::ptr::copy_nonoverlapping(ptr, buf.as_mut_ptr(), len);
        }
        buf
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

        // 1. Move heavy data to SHM H2D
        if !req.raw_input_contents.is_empty() {
             let mut shm = self.shm.lock().unwrap();
             // Just take the first one for MVP demo
             if let Some(data) = req.raw_input_contents.first() {
                 let (offset, len) = shm.write_h2d(data);
                 println!("Moved {} bytes to H2D SHM at offset {}", len, offset);
                 
                 // 2. Inject Metadata
                 if let Some(input) = req.inputs.first_mut() {
                     let params = &mut input.parameters;
                     params.insert("__shm_h2d_offset__".to_string(), pb::InferParameter {
                         parameter_choice: Some(pb::infer_parameter::ParameterChoice::Int64Param(offset as i64))
                     });
                     params.insert("__shm_h2d_len__".to_string(), pb::InferParameter {
                         parameter_choice: Some(pb::infer_parameter::ParameterChoice::Int64Param(len as i64))
                     });
                 }
                 req.raw_input_contents.clear();
             }
        }

        // 4. Forward to Python via UDS
        let mut client = self.client.clone();
        let mut response = client.model_infer(req).await?;
        
        // 5. Check response for D2H SHM metadata
        let resp_inner = response.get_mut();
        if !resp_inner.outputs.is_empty() {
             // Check metadata of first output
             if let Some(output) = resp_inner.outputs.first_mut() {
                 let params = &output.parameters;
                 if let (Some(offset_p), Some(len_p)) = (params.get("__shm_d2h_offset__"), params.get("__shm_d2h_len__")) {
                     if let (Some(pb::infer_parameter::ParameterChoice::Int64Param(offset)), 
                             Some(pb::infer_parameter::ParameterChoice::Int64Param(len))) = 
                             (&offset_p.parameter_choice, &len_p.parameter_choice) {
                         
                         let offset = *offset as usize;
                         let len = *len as usize;
                         println!("Found D2H metadata: offset={}, len={}", offset, len);
                         
                         // Read back from SHM
                         let shm = self.shm.lock().unwrap();
                         let data = shm.read_d2h(offset, len);
                         println!("Read {} bytes from D2H SHM", data.len());
                         
                         // Put into response
                         if output.contents.is_none() {
                             output.contents = Some(pb::InferTensorContents::default());
                         }
                         if let Some(contents) = &mut output.contents {
                            contents.bytes_contents.push(data);
                         }
                     }
                 }
             }
        }
        
        Ok(response)
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
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

    // Create SHM and get FDs to pass
    let shm_manager = ShmManager::new();
    let h2d_fd = shm_manager.shm_h2d.fd;
    let d2h_fd = shm_manager.shm_d2h.fd;
    println!("Created SHM segments. H2D_FD={}, D2H_FD={}", h2d_fd, d2h_fd);

    let shm_arc = Arc::new(Mutex::new(shm_manager));

    // Spawn Python Worker
    println!("Spawning Python worker with Notify FD: {}", write_fd);
    let worker_path = "worker/worker.py";
    
    let mut child = tokio::process::Command::new("uv")
        .args(&["run", "python", worker_path])
        .env("ANSERVE_READY_FD", write_fd.to_string())
        .env("ANSERVE_H2D_FD", h2d_fd.to_string())
        .env("ANSERVE_D2H_FD", d2h_fd.to_string())
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
        shm: shm_arc,
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
