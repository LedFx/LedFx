use pyo3::prelude::*;
use numpy::{PyArray3, PyReadonlyArray3, PyReadonlyArray1};
use ndarray::s;

#[pyfunction]
fn rusty_effect_process(
    image_array: PyReadonlyArray3<u8>,
    _audio_bar: f64,
    audio_pow: PyReadonlyArray1<f32>,
    intensity: f64,
    _time_passed: f64,
) -> PyResult<Py<PyArray3<u8>>> {
    Python::with_gil(|py| {
        let array = image_array.as_array();
        let mut output = array.to_owned();
        let freq_powers = audio_pow.as_array();

        // Extract frequency powers: [lows, mids, highs]
        let lows_power = (freq_powers[0] as f64 * intensity).min(1.0);
        let mids_power = (freq_powers[1] as f64 * intensity).min(1.0);
        let highs_power = (freq_powers[2] as f64 * intensity).min(1.0);

        // Get dimensions
        let (height, width, _channels) = output.dim();

        // Clear the entire image using fill - O(n) instead of O(n²)
        output.fill(0);

        // Divide matrix into three equal sections
        let section_width = width / 3;

        // Calculate bar heights based on audio power (from bottom up)
        let low_height = (lows_power * height as f64) as usize;
        let mid_height = (mids_power * height as f64) as usize;
        let high_height = (highs_power * height as f64) as usize;

        // Use ndarray slice operations for bulk assignment - much more efficient

        // Draw LOW frequency bar (RED) in left section
        if low_height > 0 && section_width > 0 {
            let start_y = height.saturating_sub(low_height);
            let mut red_region = output.slice_mut(s![start_y..height, 0..section_width, 0]);
            red_region.fill(255);
        }

        // Draw MID frequency bar (GREEN) in middle section
        if mid_height > 0 && section_width > 0 {
            let start_y = height.saturating_sub(mid_height);
            let mid_start = section_width;
            let mid_end = (section_width * 2).min(width);
            if mid_end > mid_start {
                let mut green_region = output.slice_mut(s![start_y..height, mid_start..mid_end, 1]);
                green_region.fill(255);
            }
        }

        // Draw HIGH frequency bar (BLUE) in right section
        if high_height > 0 {
            let start_y = height.saturating_sub(high_height);
            let high_start = section_width * 2;
            if width > high_start {
                let mut blue_region = output.slice_mut(s![start_y..height, high_start..width, 2]);
                blue_region.fill(255);
            }
        }

        Ok(PyArray3::from_owned_array(py, output).to_owned())
    })
}

#[pymodule]
fn ledfx_rust_effects(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rusty_effect_process, m)?)?;
    Ok(())
}
