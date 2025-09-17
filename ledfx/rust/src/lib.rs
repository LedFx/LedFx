use pyo3::prelude::*;

mod common;
mod effects;

use effects::flame2::{flame2_process, flame2_release};

#[pymodule]
fn ledfx_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(flame2_process, m)?)?;
    m.add_function(wrap_pyfunction!(flame2_release, m)?)?;
    Ok(())
}
