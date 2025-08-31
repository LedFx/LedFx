use pyo3::prelude::*;
use numpy::{PyArray3, PyReadonlyArray3, PyReadonlyArray1};
use ndarray::s;
use std::collections::HashMap;

// Constants for flame effect
const SPAWN_RATE_BASE: f32 = 0.5;
const VELOCITY_BASE: f32 = 1.0;
const MIN_LIFESPAN: f32 = 1.0;
const MAX_LIFESPAN: f32 = 4.0;
const MIN_VELOCITY_OFFSET: f32 = 0.5;
const MAX_VELOCITY_OFFSET: f32 = 2.0;
const MAX_PARTICLES_PER_BAND: usize = 2000;
const SPAWN_MODIFIER: f32 = 15.0;
const WOBBLE_RATIO: f32 = 0.1;
const TOP_TRIM_FRAC: f32 = 0.3;
const DENSITY_EXPONENT: f32 = 1.2;
const MIN_DELTA_TIME: f32 = 0.01;

// Flame effect particle structure
#[derive(Debug, Clone)]
struct Particle {
    x: f32,
    y: f32,
    age: f32,
    lifespan: f32,
    velocity_y: f32,
    size: f32,
    wobble_phase: f32,
}

#[derive(Debug)]
struct FlameState {
    particles: HashMap<usize, Vec<Particle>>,
    spawn_accum: [f32; 3],
    width: usize,
    height: usize,
}

impl FlameState {
    fn new(width: usize, height: usize) -> Self {
        let mut particles = HashMap::new();
        particles.insert(0, Vec::new());
        particles.insert(1, Vec::new());
        particles.insert(2, Vec::new());
        
        Self {
            particles,
            spawn_accum: [0.0; 3],
            width,
            height,
        }
    }
}

// Global state for flame instances
static mut FLAME_STATES: Option<HashMap<String, FlameState>> = None;

fn hsv_to_rgb(h: f32, s: f32, v: f32) -> [u8; 3] {
    let c = v * s;
    let x = c * (1.0 - ((h * 6.0) % 2.0 - 1.0).abs());
    let m = v - c;
    
    let (r_prime, g_prime, b_prime) = if h < 1.0/6.0 {
        (c, x, 0.0)
    } else if h < 2.0/6.0 {
        (x, c, 0.0)
    } else if h < 3.0/6.0 {
        (0.0, c, x)
    } else if h < 4.0/6.0 {
        (0.0, x, c)
    } else if h < 5.0/6.0 {
        (x, 0.0, c)
    } else {
        (c, 0.0, x)
    };
    
    let r = ((r_prime + m) * 255.0).round().max(0.0).min(255.0) as u8;
    let g = ((g_prime + m) * 255.0).round().max(0.0).min(255.0) as u8;
    let b = ((b_prime + m) * 255.0).round().max(0.0).min(255.0) as u8;
    
    [r, g, b]
}

fn simple_blur(output: &mut ndarray::Array3<u8>, blur_amount: usize) {
    if blur_amount == 0 { return; }
    
    let (height, width, _) = output.dim();
    let mut temp = output.clone();
    
    for _ in 0..blur_amount {
        for y in 1..height-1 {
            for x in 1..width-1 {
                for c in 0..3 {
                    let sum = output[[y-1, x, c]] as u16 + 
                              output[[y+1, x, c]] as u16 + 
                              output[[y, x-1, c]] as u16 + 
                              output[[y, x+1, c]] as u16 + 
                              (output[[y, x, c]] as u16 * 4);
                    temp[[y, x, c]] = (sum / 8) as u8;
                }
            }
        }
        *output = temp.clone();
    }
}

#[pyfunction]
fn get_flame_particle_counts(instance_id: String) -> PyResult<Vec<usize>> {
    unsafe {
        if let Some(states) = &FLAME_STATES {
            if let Some(state) = states.get(&instance_id) {
                let counts = vec![
                    state.particles.get(&0).map_or(0, |v| v.len()),
                    state.particles.get(&1).map_or(0, |v| v.len()),
                    state.particles.get(&2).map_or(0, |v| v.len()),
                ];
                Ok(counts)
            } else {
                Ok(vec![0, 0, 0])
            }
        } else {
            Ok(vec![0, 0, 0])
        }
    }
}

#[pyfunction]
fn rusty_flame_process(
    image_array: PyReadonlyArray3<u8>,
    _audio_bar: f64,
    audio_pow: PyReadonlyArray1<f32>,
    intensity: f64,
    time_passed: f64,
    spawn_rate: f64,
    velocity: f64,
    blur_amount: usize,
    instance_id: String,
) -> PyResult<Py<PyArray3<u8>>> {
    Python::with_gil(|py| {
        let array = image_array.as_array();
        let mut output = array.to_owned();
        let freq_powers = audio_pow.as_array();

        // Use parameters directly
        let spawn_rate = spawn_rate as f32;
        let velocity = velocity as f32;
        let delta = time_passed as f32;

        // Initialize global states if needed
        unsafe {
            if FLAME_STATES.is_none() {
                FLAME_STATES = Some(HashMap::new());
            }
        }

        let (height, width, _) = output.dim();
        output.fill(0);

        // Base colors for each frequency band (HSV)
        let base_colors = [
            (0.0, 1.0, 1.0),    // Red for low frequencies
            (0.33, 1.0, 1.0),   // Green for mid frequencies
            (0.67, 1.0, 1.0),   // Blue for high frequencies
        ];

        // Process particles for this instance
        unsafe {
            // Get or create state for this instance
            let states = FLAME_STATES.as_mut().unwrap();
            
            // Create new state if this instance doesn't exist or dimensions changed
            let needs_new_state = if let Some(existing_state) = states.get(&instance_id) {
                existing_state.width != width || existing_state.height != height
            } else {
                true
            };
            
            if needs_new_state {
                states.insert(instance_id.clone(), FlameState::new(width, height));
            }
            
            let state = states.get_mut(&instance_id).unwrap();
            let wobble_amplitude = (WOBBLE_RATIO * width as f32).max(1.0);
            
            // Height-based spawn scaling to match Python implementation
            let height_scale = (height as f32 / 64.0).powf(DENSITY_EXPONENT);
            
            // Use minimum delta time to ensure reasonable spawning even with very small time steps
            let effective_delta = delta.max(MIN_DELTA_TIME);

            for (band, (&power, &(h_base, s_base, v_base))) in
                freq_powers.iter().zip(base_colors.iter()).enumerate()
            {
                if band >= 3 { break; }

                let scaled_power = ((power as f64 - 0.3) * intensity * 2.0).max(0.0);
                let wobble = wobble_amplitude * (1.0 + scaled_power as f32 * 2.0);
                let scale = 1.0 + scaled_power as f32;

                let particles = state.particles.get_mut(&band).unwrap();

                // Update existing particles
                let initial_count = particles.len();
                particles.retain_mut(|p| {
                    p.age += effective_delta;
                    p.y -= (height as f32 / p.velocity_y) * effective_delta;

                    // Per-particle cutoff height
                    let cutoff = (p.wobble_phase / (2.0 * std::f32::consts::PI)) *
                               (height as f32 * TOP_TRIM_FRAC);

                    let age_ok = p.age < p.lifespan;
                    let pos_ok = p.y >= cutoff;
                    
                    age_ok && pos_ok
                });
                
                let survivors = particles.len();
                let _died = initial_count - survivors;

                // Spawn new particles (with height scaling like Python version)
                state.spawn_accum[band] += width as f32 * spawn_rate * effective_delta * SPAWN_MODIFIER * height_scale;
                let n_spawn = state.spawn_accum[band] as usize;
                state.spawn_accum[band] -= n_spawn as f32;

                if n_spawn > 0 && particles.len() < MAX_PARTICLES_PER_BAND {
                    let actual_spawn = n_spawn.min(MAX_PARTICLES_PER_BAND - particles.len());

                    for _ in 0..actual_spawn {
                        use std::collections::hash_map::DefaultHasher;
                        use std::hash::{Hash, Hasher};

                        // Simple pseudo-random using hash
                        let mut hasher = DefaultHasher::new();
                        (particles.len() + band * 1000).hash(&mut hasher);
                        let rand_val = hasher.finish();

                        particles.push(Particle {
                            x: (rand_val % width as u64) as f32,
                            y: height as f32 - 1.0,
                            age: 0.0,
                            lifespan: MIN_LIFESPAN +
                                     ((rand_val % 1000) as f32 / 1000.0) *
                                     (MAX_LIFESPAN - MIN_LIFESPAN),
                            velocity_y: 1.0 / (velocity * (MIN_VELOCITY_OFFSET +
                                       ((rand_val % 700) as f32 / 1000.0) *
                                       (MAX_VELOCITY_OFFSET - MIN_VELOCITY_OFFSET))),
                            size: 1.0 + (rand_val % 3) as f32,
                            wobble_phase: ((rand_val % 6283) as f32) / 1000.0,
                        });
                    }
                }

                // Render particles
                for particle in particles.iter() {
                    if particle.age >= particle.lifespan { continue; }

                    let t = particle.age / particle.lifespan;

                    // Color evolution over lifetime
                    let hue = (h_base * (1.0 - t)) % 1.0;
                    let sat = s_base * (1.0 - 0.5 * t);
                    let val = v_base * (1.0 - t * t);

                    let rgb = hsv_to_rgb(hue, sat, val);

                    // Apply wobble and scaling
                    let x_disp = particle.x + wobble * (t * 10.0 + particle.wobble_phase).sin();
                    let y_scaled = (height as f32 - particle.y) * scale;
                    let y_render = height as f32 - y_scaled;

                    let xi = x_disp.round() as i32;
                    let yi = y_render.round() as i32;

                    // Draw particle with size
                    let size = particle.size as i32;
                    for dy in -size..=size {
                        for dx in -size..=size {
                            let px = xi + dx;
                            let py = yi + dy;

                            if px >= 0 && px < width as i32 &&
                               py >= 0 && py < height as i32 {
                                let px = px as usize;
                                let py = py as usize;

                                // Additive blending
                                for c in 0..3 {
                                    let current = output[[py, px, c]] as u16;
                                    let new_val = current + rgb[c] as u16;
                                    output[[py, px, c]] = new_val.min(255) as u8;
                                }
                            }
                        }
                    }
                }
            }
        }

        // Apply blur
        if blur_amount > 0 {
            simple_blur(&mut output, blur_amount);
        }

        Ok(PyArray3::from_owned_array(py, output).to_owned())
    })
}

// Keep the original function for backward compatibility
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

        // Divide width into three equal sections
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
    m.add_function(wrap_pyfunction!(rusty_flame_process, m)?)?;
    m.add_function(wrap_pyfunction!(get_flame_particle_counts, m)?)?;
    Ok(())
}
