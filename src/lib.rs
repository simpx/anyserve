//! anyServe Core Library
//!
//! This module is kept for potential future Python bindings.
//! The main functionality is now in main.rs (anyserve-node binary).

pub mod pb {
    tonic::include_proto!("anyserve");
}
