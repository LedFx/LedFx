use pyo3::prelude::*;

mod common;
mod effects;

use effects::flame2::flame2_process;

#[pymodule]
fn ledfx_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(flame2_process, m)?)?;
    Ok(())
}
