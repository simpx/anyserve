use pyo3::prelude::*;
use std::fs;
use std::path::PathBuf;
use uuid::Uuid;
use std::io::Write;

#[pyclass]
struct AnyserveCore {
    root_dir: PathBuf,
    instance_id: String,
}

#[pymethods]
impl AnyserveCore {
    #[new]
    fn new(root_dir: String, instance_id: String) -> PyResult<Self> {
        let root = PathBuf::from(&root_dir);
        let instance_path = root.join("instances").join(&instance_id).join("objects");
        let names_path = root.join("names");

        fs::create_dir_all(&instance_path)?;
        fs::create_dir_all(&names_path)?;

        Ok(AnyserveCore {
            root_dir: root,
            instance_id,
        })
    }

    fn put_object(&self, data: Vec<u8>) -> PyResult<String> {
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

    fn get_object(&self, object_id: String, owner_id: String) -> PyResult<Vec<u8>> {
        let path = self
            .root_dir
            .join("instances")
            .join(owner_id)
            .join("objects")
            .join(object_id);
            
        let data = fs::read(path)?;
        Ok(data)
    }

    fn register_service(&self, service_name: String) -> PyResult<()> {
        let service_dir = self.root_dir.join("names").join(&service_name);
        fs::create_dir_all(&service_dir)?;
        
        let instance_file = service_dir.join(&self.instance_id);
        fs::File::create(instance_file)?;
        
        Ok(())
    }

    fn lookup_service(&self, service_name: String) -> PyResult<Vec<String>> {
        let service_dir = self.root_dir.join("names").join(&service_name);
        let mut instances = Vec::new();

        if service_dir.exists() {
            for entry in fs::read_dir(service_dir)? {
                let entry = entry?;
                let file_name = entry.file_name();
                if let Some(name) = file_name.to_str() {
                    instances.push(name.to_string());
                }
            }
        }
        Ok(instances)
    }
    
    fn get_instance_id(&self) -> String {
        self.instance_id.clone()
    }
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<AnyserveCore>()?;
    Ok(())
}
