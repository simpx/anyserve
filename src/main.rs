// src/main.rs
use std::env;
use std::ffi::CString;
use std::os::unix::io::{FromRawFd, RawFd};
use std::path::Path;
use std::process::Stdio;
use std::ptr;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use libc::{c_void, off_t};
use tokio::io::AsyncReadExt;
use tonic::transport::{Endpoint, Server, Uri};
use tonic::{Request, Response, Status};
use tower::service_fn;
use uuid::Uuid;
use hyper_util::rt::tokio::TokioIo;

pub mod pb {
    // Include the KServe v2 proto
    tonic::include_proto!("inference");
}

use pb::grpc_inference_service_server::{GrpcInferenceService, GrpcInferenceServiceServer};
use pb::{ModelInferRequest, ModelInferResponse};

const SHM_SIZE: usize = 10 * 1024 * 1024; // 10MB

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
            libc::shm_unlink(name.as_ptr());

            // 2b. Clear FD_CLOEXEC so child inherits it
            let flags = libc::fcntl(fd, libc::F_GETFD);
            if flags >= 0 {
                libc::fcntl(fd, libc::F_SETFD, flags & !libc::FD_CLOEXEC);
            }

            // 3. Resize
            if libc::ftruncate(fd, size as off_t) < 0 {
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
                0,
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
            libc::munmap(self.ptr as *mut c_void, self.size);
            libc::close(self.fd);
        }
    }
}

struct ShmManager {
    shm_h2d: RawShm, // Host to Device (Rust -> Python)
    shm_d2h: RawShm, // Device to Host (Python -> Rust)
}

impl ShmManager {
    fn new() -> Self {
        let shm_h2d = RawShm::new(SHM_SIZE).expect("Failed to create H2D SHM");
        let shm_d2h = RawShm::new(SHM_SIZE).expect("Failed to create D2H SHM");
        ShmManager { shm_h2d, shm_d2h }
    }
}

pub struct ProxyService {
    shm: Arc<Mutex<ShmManager>>,
    client: pb::grpc_inference_service_client::GrpcInferenceServiceClient<tonic::transport::Channel>,
}

impl ProxyService {
    async fn connect_worker(uds_path: &str) -> Result<pb::grpc_inference_service_client::GrpcInferenceServiceClient<tonic::transport::Channel>, Box<dyn std::error::Error>> {
        let uds_path = uds_path.to_string();
        // We will ignore this uri because AsyncConnect ignores it
        let channel = Endpoint::try_from("http://[::]:50051")?
            .connect_with_connector(service_fn(move |_: Uri| {
                let uds_path = uds_path.clone();
                async move {
                    // Wait for socket to appear?
                    let stream = tokio::net::UnixStream::connect(uds_path).await?;
                    Ok::<_, std::io::Error>(TokioIo::new(stream))
                }
            }))
            .await?;

        Ok(pb::grpc_inference_service_client::GrpcInferenceServiceClient::new(channel))
    }
}

#[tonic::async_trait]
impl GrpcInferenceService for ProxyService {
    async fn server_live(
        &self,
        request: Request<pb::ServerLiveRequest>,
    ) -> Result<Response<pb::ServerLiveResponse>, Status> {
        let mut client = self.client.clone();
        client.server_live(request).await
    }

    async fn server_ready(
        &self,
        request: Request<pb::ServerReadyRequest>,
    ) -> Result<Response<pb::ServerReadyResponse>, Status> {
        let mut client = self.client.clone();
        client.server_ready(request).await
    }

    async fn model_ready(
        &self,
        request: Request<pb::ModelReadyRequest>,
    ) -> Result<Response<pb::ModelReadyResponse>, Status> {
        let mut client = self.client.clone();
        client.model_ready(request).await
    }

    async fn server_metadata(
        &self,
        request: Request<pb::ServerMetadataRequest>,
    ) -> Result<Response<pb::ServerMetadataResponse>, Status> {
        let mut client = self.client.clone();
        client.server_metadata(request).await
    }

    async fn model_metadata(
        &self,
        request: Request<pb::ModelMetadataRequest>,
    ) -> Result<Response<pb::ModelMetadataResponse>, Status> {
        let mut client = self.client.clone();
        client.model_metadata(request).await
    }

    async fn model_infer(
        &self,
        request: Request<ModelInferRequest>,
    ) -> Result<Response<ModelInferResponse>, Status> {
        // Here we can intercept inputs and move them to SHM if needed
        // For MVP, we just proxy everything
        let mut client = self.client.clone();
        client.model_infer(request).await
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Parse arguments manually for MVP:
    // anyserve [OPTIONS] <APP_STR>
    // Options: --port <PORT>
    
    let args: Vec<String> = env::args().collect();
    let mut target = String::new();
    let mut port = 8080;
    
    let mut i = 1;
    while i < args.len() {
        let arg = &args[i];
        if arg == "--port" {
            if i + 1 < args.len() {
                 port = args[i+1].parse().unwrap_or(8080);
                 i += 1;
            }
        } else if !arg.starts_with("-") {
            // Assume positional arg is target if we haven't found one yet
            if target.is_empty() {
                target = arg.clone();
            }
        }
        i += 1;
    }

    // 1. Generate Random UDS Path
    let uds_path = format!("/tmp/anyserve_worker_{}.sock", Uuid::new_v4().simple());
    
    // Cleanup existing (shouldn't happen with random UUID)
    if Path::new(&uds_path).exists() {
        let _ = std::fs::remove_file(&uds_path);
    }

    println!("Using UDS Path: {}", uds_path);

    // 2. Create Pipe for Readiness
    let mut fds: [RawFd; 2] = [0; 2];
    unsafe {
        if libc::pipe(fds.as_mut_ptr()) < 0 {
            return Err("Failed to create pipe".into());
        }
    }
    let read_fd = fds[0];
    let write_fd = fds[1];

    // 3. Create SHM
    let shm_manager = ShmManager::new();
    let h2d_fd = shm_manager.shm_h2d.fd;
    let d2h_fd = shm_manager.shm_d2h.fd;
    println!("Created SHM segments. H2D_FD={}, D2H_FD={}", h2d_fd, d2h_fd);
    
    let shm_arc = Arc::new(Mutex::new(shm_manager));

    // 4. Spawn Python Worker
    println!("Spawning Python worker with Notify FD: {}", write_fd);
    let python_path = env::var("PYTHON_PATH").unwrap_or_else(|_| "python".to_string());
    
    // Determine worker command logic
    // 1. If `target` (CLI arg) is set -> python -m anyserve_worker.loader <target>
    // 2. Else -> default environment logic
    let python_args = if !target.is_empty() {
        println!("Launching target app: {}", target);
        vec!["-m".to_string(), "anyserve_worker.loader".to_string(), target]
    } else if let Ok(script) = env::var("ANSERVE_WORKER_SCRIPT") {
        vec![script]
    } else if let Ok(module) = env::var("ANSERVE_WORKER_MODULE") {
        vec!["-m".to_string(), module]
    } else {
        // Fallback or Help? For now default echo
        vec!["-m".to_string(), "anyserve_worker".to_string()]
    };

    let mut child = tokio::process::Command::new(&python_path)
        .args(&python_args)
        .env("ANSERVE_WORKER_UDS", &uds_path)
        .env("ANSERVE_READY_FD", write_fd.to_string())
        .env("ANSERVE_H2D_FD", h2d_fd.to_string())
        .env("ANSERVE_D2H_FD", d2h_fd.to_string())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("Failed to spawn python worker");
    
    // Close write end in parent
    unsafe { libc::close(write_fd); }

    // 5. Wait for Readiness
    println!("Waiting for worker signal...");
    let mut pipe_reader = unsafe { tokio::fs::File::from_raw_fd(read_fd) };
    let mut buf = [0u8; 16];
    
    match tokio::time::timeout(Duration::from_secs(10), pipe_reader.read(&mut buf)).await {
        Ok(Ok(n)) if n > 0 => {
             let signal = String::from_utf8_lossy(&buf[..n]);
             println!("Worker signaled: {}", signal.trim());
        },
        _ => {
            let _ = child.kill().await;
            return Err("Worker failed to signal readiness".into());
        }
    }

    // 6. Connect to Worker
    let client = ProxyService::connect_worker(&uds_path).await?;
    println!("Connected to Python Worker via UDS");

    let service = ProxyService {
        shm: shm_arc,
        client,
    };

    // 7. Start External Server
    let addr = format!("0.0.0.0:{}", port).parse()?;
    println!("Global Server listening on {}", addr);

    let server_future = Server::builder()
        .add_service(GrpcInferenceServiceServer::new(service))
        .serve(addr);

    // Run server and check child status in parallel
    // If child exits, we should exit
    tokio::select! {
        _ = server_future => {},
        _ = child.wait() => {
            println!("Worker process exited unexpectedly");
        }
    }

    // Cleanup
    let _ = std::fs::remove_file(&uds_path);
    let _ = child.kill().await;

    Ok(())
}
