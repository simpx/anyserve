use axum::{
    debug_handler,
    extract::{State, Request},
    routing::any,
    Router, 
    body::Body,
    http::StatusCode,
    response::{Response, IntoResponse},
};
use std::{
    process::Child, 
    sync::{Arc, atomic::{AtomicUsize, Ordering}},
    path::PathBuf,
};
use std::process::Command;
use std::time::Duration;
use hyper_util::{
    client::legacy::Client,
    client::legacy::connect::{Connected, Connection},
    rt::TokioExecutor,
};
use tower::service_fn;
use tokio::net::UnixStream;
use shared_memory::ShmemConf;
use uuid::Uuid;
use http_body_util::BodyExt;

// Wrapper to make Shmem Send/Sync since it contains raw pointers but logic handles ownership
struct SendShmem(shared_memory::Shmem);
unsafe impl Send for SendShmem {}
unsafe impl Sync for SendShmem {} // Safe because we just hold ownership

struct WorkerProcess {
    _process: Child,
}

struct WorkerInfo {
    socket_path: String,
}

struct AppState {
    workers: Vec<WorkerInfo>,
    counter: AtomicUsize,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    println!("=== AnyServe Rust Runtime (Zero-Copy Edition) ===");
    println!("Architecture: Rust (Writer) -> Shared Memory -> Python (Reader)");
    
    let tmp_dir = PathBuf::from("tmp_sockets");
    if tmp_dir.exists() {
        std::fs::remove_dir_all(&tmp_dir)?;
    }
    std::fs::create_dir(&tmp_dir)?;

    let worker_count = 3;
    let python_script = "app.py"; 

    println!("Starting {} instances...", worker_count);

    let mut worker_processes = Vec::new();
    let mut worker_infos = Vec::new();

    for i in 0..worker_count {
        let socket_name = format!("worker_{}.sock", i);
        let socket_path = tmp_dir.join(&socket_name);
        let socket_path_str = socket_path.to_string_lossy().to_string();

        println!(" -> Spawning Worker-{} on {}", i + 1, socket_path_str);
        
        let child = Command::new("python3")
            .arg("-u") 
            .arg(python_script)
            .arg("--socket")
            .arg(&socket_path_str)
            .spawn()
            .expect("Failed to spawn python worker");
            
        worker_processes.push(WorkerProcess {
            _process: child,
        });
        worker_infos.push(WorkerInfo {
            socket_path: socket_path_str,
        });
    }

    tokio::time::sleep(Duration::from_secs(1)).await;

    let state = Arc::new(AppState {
        workers: worker_infos,
        counter: AtomicUsize::new(0),
    });

    let app = Router::new()
        .route("/", any(proxy_handler))
        .route("/*path", any(proxy_handler))
        .with_state(state);

    let ingress_port = 3000;
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", ingress_port)).await?;
    println!("\n🚀 Runtime Ready! Entrypoint: http://localhost:{}", ingress_port);
    axum::serve(listener, app).await?;

    Ok(())
}

#[debug_handler]
async fn proxy_handler(
    State(state): State<Arc<AppState>>,
    req: Request,
) -> impl IntoResponse {
    
    let count = state.counter.fetch_add(1, Ordering::SeqCst);
    let worker_idx = count % state.workers.len();
    let socket_path = state.workers[worker_idx].socket_path.clone();

    let (parts, body) = req.into_parts();
    let path = parts.uri.path().to_string();
    let method = parts.method.clone();

    let body_bytes = axum::body::to_bytes(body, 100 * 1024 * 1024).await
        .map_err(|_| StatusCode::BAD_REQUEST)?;

    let shmem_info = if !body_bytes.is_empty() {
        let shm_uuid = Uuid::new_v4();
        // Safe length for MacOS shm names, must start with /
        let shm_os_id = format!("/anyserve-{}", &shm_uuid.simple().to_string()[..8]); 
        
        // Create SHM
        let shmem = match ShmemConf::new()
            .size(body_bytes.len())
            .os_id(&shm_os_id)
            .create() 
        {
            Ok(m) => SendShmem(m), // Wrap it
            Err(e) => {
                eprintln!("Unable to create shm: {}", e);
                return Err(StatusCode::INTERNAL_SERVER_ERROR);
            }
        };

        unsafe {
            let ptr = shmem.0.as_ptr(); // Access inner
            std::ptr::copy_nonoverlapping(body_bytes.as_ptr(), ptr, body_bytes.len());
        }

        Some((shm_os_id, body_bytes.len(), shmem))
    } else {
        None
    };

    // Construct upstream URI with original path
    let uri_string = format!("http://localhost{}", path);
    let url = uri_string.parse::<hyper::Uri>().unwrap();
    
    let mut upstream_req = axum::http::Request::builder()
        .method(method)
        .uri(url)
        .header("Content-Type", "application/json");

    if let Some((ref id, size, _)) = shmem_info {
        upstream_req = upstream_req
            .header("X-Shm-Key", id)
            .header("X-Shm-Size", size.to_string());
    }

    let upstream_req = upstream_req
        .body(Body::empty()) 
        .unwrap();

    let connector = service_fn(move |_| {
        let path = PathBuf::from(socket_path.clone());
        Box::pin(async move {
            let stream = UnixStream::connect(path).await?;
            Ok::<_, std::io::Error>(TokioIo::new(stream))
        })
    });

    let client = Client::builder(TokioExecutor::new())
        .build(connector);

    match client.request(upstream_req).await {
        Ok(resp) => {
             let status = resp.status();
             let bytes = resp.into_body().collect().await
                 .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
                 .to_bytes();
             
             Ok(Response::builder()
                .status(status)
                .header("Content-Type", "application/json") 
                .body(Body::from(bytes))
                .unwrap())
        },
        Err(e) => {
            eprintln!("Worker error: {}", e);
            Err(StatusCode::BAD_GATEWAY)
        }
    }
}

use hyper::rt::{Read, Write};
use std::pin::Pin;
use std::task::{Context, Poll};

struct TokioIo<T>(T);

impl<T> TokioIo<T> {
    pub fn new(inner: T) -> Self {
        Self(inner)
    }
}

impl<T> Connection for TokioIo<T> {
    fn connected(&self) -> Connected {
        Connected::new()
    }
}

impl<T> Read for TokioIo<T>
where
    T: tokio::io::AsyncRead + Unpin,
{
    fn poll_read(
        mut self: Pin<&mut Self>,
        cx: &mut Context<'_>,
        mut buf: hyper::rt::ReadBufCursor<'_>,
    ) -> Poll<Result<(), std::io::Error>> {
        let n = unsafe {
            let mut tbuf = tokio::io::ReadBuf::uninit(buf.as_mut());
            match tokio::io::AsyncRead::poll_read(Pin::new(&mut self.0), cx, &mut tbuf) {
                Poll::Ready(Ok(())) => tbuf.filled().len(),
                other => return other,
            }
        };

        unsafe {
            buf.advance(n);
        }
        Poll::Ready(Ok(()))
    }
}

impl<T> Write for TokioIo<T>
where
    T: tokio::io::AsyncWrite + Unpin,
{
    fn poll_write(
        mut self: Pin<&mut Self>,
        cx: &mut Context<'_>,
        buf: &[u8],
    ) -> Poll<Result<usize, std::io::Error>> {
        tokio::io::AsyncWrite::poll_write(Pin::new(&mut self.0), cx, buf)
    }

    fn poll_flush(
        mut self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Result<(), std::io::Error>> {
        tokio::io::AsyncWrite::poll_flush(Pin::new(&mut self.0), cx)
    }

    fn poll_shutdown(
        mut self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Result<(), std::io::Error>> {
        tokio::io::AsyncWrite::poll_shutdown(Pin::new(&mut self.0), cx)
    }
}
