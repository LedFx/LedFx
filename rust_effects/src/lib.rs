use pyo3::prelude::*;
use numpy::{PyArray3, PyReadonlyArray3, PyReadonlyArray1};
use std::collections::HashMap;

// Simple linear congruential generator for better randomness
#[derive(Debug)]
struct SimpleRng {
    state: u64,
}

impl SimpleRng {
    fn new(seed: u64) -> Self {
        Self {
            state: seed.wrapping_mul(1103515245).wrapping_add(12345)
        }
    }

    fn next(&mut self) -> u64 {
        self.state = self.state.wrapping_mul(1103515245).wrapping_add(12345);
        self.state
    }

    fn next_f32(&mut self) -> f32 {
        // Optimized: avoid division by pre-computing the multiplier
        (self.next() >> 32) as f32 * (1.0 / u32::MAX as f32)
    }

    fn next_range(&mut self, min: f32, max: f32) -> f32 {
        // Optimized: compute range once
        let range = max - min;
        min + self.next_f32() * range
    }

    fn next_int(&mut self, max: u32) -> u32 {
        ((self.next() >> 32) % max as u64) as u32
    }

    // Generate velocity with realistic distribution - optimized version
    fn next_velocity_offset(&mut self, min: f32, max: f32) -> f32 {
        // Simplified triangular distribution using single random number
        let r = self.next_f32();
        let range = max - min;

        // Use a simple curve to bias toward middle values
        let biased_r = if r < 0.5 {
            2.0 * r * r // Quadratic curve for first half
        } else {
            1.0 - 2.0 * (1.0 - r) * (1.0 - r) // Inverse quadratic for second half
        };

        min + biased_r * range
    }
}

// Helper function to convert RGB to HSV
fn rgb_to_hsv(r: u8, g: u8, b: u8) -> (f32, f32, f32) {
    let r = r as f32 / 255.0;
    let g = g as f32 / 255.0;
    let b = b as f32 / 255.0;

    let max = r.max(g).max(b);
    let min = r.min(g).min(b);
    let delta = max - min;

    let h = if delta == 0.0 {
        0.0
    } else if max == r {
        60.0 * (((g - b) / delta) % 6.0)
    } else if max == g {
        60.0 * ((b - r) / delta + 2.0)
    } else {
        60.0 * ((r - g) / delta + 4.0)
    };

    let h = if h < 0.0 { h + 360.0 } else { h } / 360.0; // Normalize to 0-1
    let s = if max == 0.0 { 0.0 } else { delta / max };
    let v = max;

    (h, s, v)
}

// Calculate appropriate particle size range based on matrix dimensions
fn calculate_particle_size_range(width: usize, height: usize) -> (f32, f32) {
    // Use the smaller dimension as the basis for scaling
    let base_dimension = width.min(height) as f32;

    // Reference size: For a 64x64 matrix, particles should be 1-4 pixels
    let scale_factor = base_dimension / 64.0;

    // Base size ranges from 1.0 to 4.0 at reference scale
    let min_size = (1.0 * scale_factor).max(1.0);
    let max_size = (4.0 * scale_factor).max(1.0);

    // For very small matrices, cap the maximum size
    if base_dimension < 32.0 {
        (min_size, max_size.min(2.0))
    } else {
        (min_size, max_size.min(base_dimension * 0.1))
    }
}

// Constants for flame effect
const MIN_LIFESPAN: f32 = 2.0;
const MAX_LIFESPAN: f32 = 4.0;
const MIN_VELOCITY_OFFSET: f32 = 0.3;  // Increased range: slower particles
const MAX_VELOCITY_OFFSET: f32 = 1.8;  // Increased range: faster particles
const MAX_PARTICLES_PER_BAND: usize = 4096;  // Match Python INIT_CAP
const SPAWN_MODIFIER: f32 = 4.0;  // Match Python: was 15.0
const WOBBLE_RATIO: f32 = 0.05;  // Match Python: was 0.1
const TOP_TRIM_FRAC: f32 = 0.4;  // Match Python: was 0.3
const DENSITY_EXPONENT: f32 = 0.5;  // Match Python: was 1.2
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
    rng: SimpleRng,
}

impl FlameState {
    fn new(width: usize, height: usize, instance_id: u64) -> Self {
        let mut particles = HashMap::new();
        particles.insert(0, Vec::new());
        particles.insert(1, Vec::new());
        particles.insert(2, Vec::new());

        // Create unique seed for this instance using current time + instance_id
        use std::time::{SystemTime, UNIX_EPOCH};
        let time_seed = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos() as u64;
        let seed = time_seed.wrapping_add(instance_id.wrapping_mul(123456789));

        Self {
            particles,
            spawn_accum: [0.0; 3],
            width,
            height,
            rng: SimpleRng::new(seed),
        }
    }
}

// Global state for flame instances
static mut FLAME_STATES: Option<HashMap<u64, FlameState>> = None;

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

    // Optimized blur with fewer iterations for performance
    let actual_iterations = blur_amount.min(2); // Cap blur iterations

    for _ in 0..actual_iterations {
        // Use slice operations for better performance
        for y in 1..height-1 {
            for x in 1..width-1 {
                // Process all 3 color channels at once
                let center = [output[[y, x, 0]], output[[y, x, 1]], output[[y, x, 2]]];
                let up = [output[[y-1, x, 0]], output[[y-1, x, 1]], output[[y-1, x, 2]]];
                let down = [output[[y+1, x, 0]], output[[y+1, x, 1]], output[[y+1, x, 2]]];
                let left = [output[[y, x-1, 0]], output[[y, x-1, 1]], output[[y, x-1, 2]]];
                let right = [output[[y, x+1, 0]], output[[y, x+1, 1]], output[[y, x+1, 2]]];

                for c in 0..3 {
                    let sum = up[c] as u16 + down[c] as u16 + left[c] as u16 + right[c] as u16 + (center[c] as u16 * 4);
                    temp[[y, x, c]] = (sum / 8) as u8;
                }
            }
        }
        std::mem::swap(output, &mut temp); // Avoid clone
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
    instance_id: u64,
    low_color: (u8, u8, u8),
    mid_color: (u8, u8, u8),
    high_color: (u8, u8, u8),
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

        // Convert RGB colors to HSV for each frequency band
        let base_colors = [
            rgb_to_hsv(low_color.0, low_color.1, low_color.2),   // Low frequencies
            rgb_to_hsv(mid_color.0, mid_color.1, mid_color.2),   // Mid frequencies
            rgb_to_hsv(high_color.0, high_color.1, high_color.2), // High frequencies
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
                states.insert(instance_id, FlameState::new(width, height, instance_id));
            }

            let state = states.get_mut(&instance_id).unwrap();
            let wobble_amplitude = (WOBBLE_RATIO * width as f32).max(1.0);

            // Pre-calculate particle size range for performance
            let (min_particle_size, max_particle_size) = calculate_particle_size_range(width, height);

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

                // Pre-compute base RGB color once per band for maximum performance
                let base_rgb = hsv_to_rgb(h_base, s_base, v_base);

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

                    for _i in 0..actual_spawn {
                        particles.push(Particle {
                            x: state.rng.next_range(0.0, width as f32),
                            y: height as f32 - 1.0,
                            age: 0.0,
                            lifespan: state.rng.next_range(MIN_LIFESPAN, MAX_LIFESPAN),
                            velocity_y: 1.0 / (velocity * state.rng.next_velocity_offset(MIN_VELOCITY_OFFSET, MAX_VELOCITY_OFFSET)),
                            size: state.rng.next_range(min_particle_size, max_particle_size),
                            wobble_phase: state.rng.next_range(0.0, 2.0 * std::f32::consts::PI),
                        });
                    }
                }

                // Render particles with simpler approach for better performance
                for particle in particles.iter() {
                    if particle.age >= particle.lifespan { continue; }

                    let t = particle.age / particle.lifespan;

                    // More aggressive fading - particles get darker sooner
                    // Use exponential curve to fade to near-black before disappearing
                    let fade = (1.0 - t).powf(1.5); // Exponential fade - gets darker faster
                    let rgb = [
                        (base_rgb[0] as f32 * fade) as u8,
                        (base_rgb[1] as f32 * fade) as u8,
                        (base_rgb[2] as f32 * fade) as u8,
                    ];

                    // Apply wobble and scaling
                    let x_disp = particle.x + wobble * (t * 10.0 + particle.wobble_phase).sin();
                    let y_scaled = (height as f32 - particle.y) * scale;
                    let y_render = height as f32 - y_scaled;

                    let xi = x_disp.round() as i32;
                    let yi = y_render.round() as i32;

                    // Shrink particle size as it fades (embers get smaller as they die)
                    let shrunk_size = particle.size * fade.sqrt(); // Square root gives gentler size reduction
                    let size = shrunk_size as i32;
                    let size_f = shrunk_size;
                    let size_squared = size_f * size_f;

                    // Calculate safe bounds in i32 space first
                    let y_start_i32 = (yi - size).max(0);
                    let y_end_i32 = (yi + size + 1).min(height as i32);
                    let x_start_i32 = (xi - size).max(0);
                    let x_end_i32 = (xi + size + 1).min(width as i32);

                    // Only proceed if we have valid bounds
                    if y_start_i32 < y_end_i32 && x_start_i32 < x_end_i32 &&
                       y_start_i32 >= 0 && y_end_i32 <= height as i32 &&
                       x_start_i32 >= 0 && x_end_i32 <= width as i32 {

                        // Now convert to usize safely
                        let y_start = y_start_i32 as usize;
                        let y_end = y_end_i32 as usize;
                        let x_start = x_start_i32 as usize;
                        let x_end = x_end_i32 as usize;

                        // Draw circular particle using squared distance for smooth edges
                        for py in y_start..y_end {
                            let dy = (py as i32) - yi;
                            let dy_sq = (dy * dy) as f32;

                            for px in x_start..x_end {
                                let dx = (px as i32) - xi;
                                let dx_sq = (dx * dx) as f32;
                                let dist_squared = dx_sq + dy_sq;

                                // Only draw if within circular particle radius
                                if dist_squared <= size_squared {
                                    // Smooth circular falloff for nice particle edges
                                    let intensity = (1.0 - (dist_squared / size_squared)).max(0.0);

                                    // Apply intensity to color and blend additively
                                    for c in 0..3 {
                                        let current = output[[py, px, c]] as u16;
                                        let contribution = (rgb[c] as f32 * intensity) as u16;
                                        let new_val = current + contribution;
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

#[pymodule]
fn ledfx_rust_effects(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rusty_flame_process, m)?)?;
    Ok(())
}
