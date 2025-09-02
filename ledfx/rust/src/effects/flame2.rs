use pyo3::prelude::*;
use numpy::{PyArray3, PyReadonlyArray3, PyReadonlyArray1};
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use crate::common::{SimpleRng, simple_blur};

// Constants for flame effect
const MIN_LIFESPAN: f32 = 1.5;  // Shorter lifespan for more dynamic flames
const MAX_LIFESPAN: f32 = 3.5;
const MIN_VELOCITY_OFFSET: f32 = 0.2;  // More velocity variation
const MAX_VELOCITY_OFFSET: f32 = 2.5;
const MAX_PARTICLES_PER_BAND: usize = 4096;
const SPAWN_MODIFIER: f32 = 5.0;  // Slightly more particles
const WOBBLE_RATIO: f32 = 0.08;  // More wobble for flame-like motion
const TOP_TRIM_FRAC: f32 = 0.35;  // Keep more flame height
const DENSITY_EXPONENT: f32 = 0.6;  // Better density scaling
const MIN_DELTA_TIME: f32 = 0.01;

// New constants for fire-like behavior
const ACCELERATION_FACTOR: f32 = 0.3;  // Particles accelerate as they rise
const TURBULENCE_STRENGTH: f32 = 0.15;  // Random motion strength
const FLICKER_INTENSITY: f32 = 0.2;  // Random brightness variation

// Flame effect particle structure
#[derive(Debug, Clone)]
struct Particle {
    x: f32,
    y: f32,
    age: f32,
    lifespan: f32,
    velocity_y: f32,
    velocity_x: f32,  // Horizontal velocity for turbulence
    size: f32,
    wobble_phase: f32,
    turbulence_phase: f32,  // For random motion
    initial_brightness: f32,  // Starting brightness for flickering
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

// Global state for flame instances - using thread-safe approach
static FLAME_STATES: OnceLock<Mutex<HashMap<u64, FlameState>>> = OnceLock::new();

// Memory cleanup function (currently unused due to PyO3 export issues)
// The HashMap will grow over time, but effect instances are typically long-lived
// and the memory impact is minimal (each state is small)
#[allow(dead_code)]
fn flame2_release(instance_id: u64) -> PyResult<()> {
    if let Some(m) = FLAME_STATES.get() {
        if let Ok(mut states) = m.lock() {
            states.remove(&instance_id);
        }
    }
    Ok(())
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

// Calculate fire-like color temperature progression
fn get_fire_color(base_hsv: (f32, f32, f32), age_factor: f32, height_factor: f32) -> (f32, f32, f32) {
    let (h_base, s_base, v_base) = base_hsv;

    // Fire typically goes from yellow/orange (hot) at bottom to red (cool) at top
    // and dims as particles age
    let temperature_shift = (age_factor + height_factor * 0.6).min(1.0);

    // Shift hue towards red as flame rises and ages
    let h = if h_base < 0.1 || h_base > 0.9 { // If base is red-ish
        h_base + temperature_shift * 0.05  // Shift slightly more red
    } else if h_base < 0.2 { // If base is orange-ish
        h_base + temperature_shift * 0.15  // Shift more towards red
    } else { // Other colors
        h_base + temperature_shift * 0.1
    };

    // Increase saturation slightly for more vibrant flames
    let s = (s_base + temperature_shift * 0.1).min(1.0);

    // Reduce value (brightness) as particle ages, but keep some minimum
    let v = v_base * (1.0 - temperature_shift * 0.4).max(0.2);

    (h % 1.0, s, v)
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

#[pyfunction]
pub fn flame2_process(
    image_array: PyReadonlyArray3<u8>,
    _audio_bar: f64,
    audio_pow: PyReadonlyArray1<f32>,
    intensity: f64,
    time_passed: f64,
    spawn_rate: f64,
    velocity: f64,
    blur_amount: usize,
    instance_id: u64,
    low_color: PyReadonlyArray1<f64>,
    mid_color: PyReadonlyArray1<f64>,
    high_color: PyReadonlyArray1<f64>,
    animation_speed: f64,
) -> PyResult<Py<PyArray3<u8>>> {
    Python::with_gil(|py| {
        // STEP 1: Clone/copy Python data while holding GIL
        let mut output = image_array.as_array().to_owned();
        let freq_powers_owned: Vec<f32> = audio_pow.as_array().to_vec();
        let low_rgb = low_color.as_array().to_vec();
        let mid_rgb = mid_color.as_array().to_vec();
        let high_rgb = high_color.as_array().to_vec();

        // Use parameters directly with animation speed scaling
        let spawn_rate = spawn_rate as f32;
        let velocity = velocity as f32;
        let animation_speed = animation_speed as f32;

        // Enhanced scaling with exponential curve for much better low-end control:
        // - At 0.1: 0.001x speed (extremely slow)
        // - At 0.3: 0.027x speed (very slow)
        // - At 0.5: 0.125x speed (eighth speed)
        // - At 1.0: full speed
        // Note: animation_speed is clamped to minimum 0.1 in Python schema
        let speed_multiplier = animation_speed * animation_speed * animation_speed;
        let delta = (time_passed as f32) * speed_multiplier;

        let (height, width, _) = output.dim();
        output.fill(0);

        // Precompute base HSV colors while holding GIL
        let base_colors = [
            rgb_to_hsv(low_rgb[0] as u8, low_rgb[1] as u8, low_rgb[2] as u8),
            rgb_to_hsv(mid_rgb[0] as u8, mid_rgb[1] as u8, mid_rgb[2] as u8),
            rgb_to_hsv(high_rgb[0] as u8, high_rgb[1] as u8, high_rgb[2] as u8),
        ];

        // STEP 2: Release GIL for heavy computation
        py.allow_threads(|| {
            // All particle processing happens here WITHOUT the GIL
            // This allows other Python threads to run while we compute
        {
            // Get or initialize the global states map
            let states_mutex = FLAME_STATES.get_or_init(|| Mutex::new(HashMap::new()));
            let mut states = states_mutex.lock().unwrap();

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
                freq_powers_owned.iter().zip(base_colors.iter()).enumerate()
            {
                if band >= 3 { break; }

                let scaled_power = ((power as f64 - 0.3) * intensity * 2.0).max(0.0);
                let wobble = wobble_amplitude * (1.0 + scaled_power as f32 * 2.0);
                let scale = 1.0 + scaled_power as f32;

                let particles = state.particles.get_mut(&band).unwrap();

                // Pre-compute base RGB color once per band for maximum performance
                let _base_rgb = hsv_to_rgb(h_base, s_base, v_base);

                // Update existing particles with fire-like physics
                let initial_count = particles.len();
                particles.retain_mut(|p| {
                    p.age += effective_delta;

                    // Fire particles accelerate as they rise (buoyancy effect)
                    let acceleration = 1.0 + p.age * ACCELERATION_FACTOR;

                    // Movement speed: particles should traverse screen in about 1 second at full speed
                    // This allows proper flame height while still aging naturally
                    let base_movement_speed = height as f32 * 1.2; // 1.2x screen height per second
                    p.y -= (base_movement_speed * velocity / p.velocity_y) * effective_delta * acceleration;

                    // Add turbulence for chaotic flame motion
                    p.turbulence_phase += effective_delta * 8.0; // Faster phase change
                    let turbulence_x = TURBULENCE_STRENGTH * p.turbulence_phase.sin() * height as f32 * effective_delta;
                    let turbulence_y = TURBULENCE_STRENGTH * (p.turbulence_phase * 1.3).cos() * height as f32 * effective_delta * 0.5;

                    p.x += p.velocity_x * effective_delta * width as f32 + turbulence_x;
                    p.y += turbulence_y; // Small vertical turbulence

                    // Wrap horizontal position
                    if p.x < 0.0 { p.x += width as f32; }
                    if p.x >= width as f32 { p.x -= width as f32; }

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
                        // Adjust lifespan inversely to animation speed so particles can reach the same height
                        // At full speed (1.0): normal lifespan
                        // At half speed (0.5): double lifespan
                        // At minimum speed (0.1): 10x lifespan
                        // Note: animation_speed is clamped to minimum 0.1 in Python schema
                        let base_lifespan = state.rng.next_range(MIN_LIFESPAN, MAX_LIFESPAN);
                        let adjusted_lifespan = base_lifespan / animation_speed;

                        particles.push(Particle {
                            x: state.rng.next_range(0.0, width as f32),
                            y: height as f32 - 1.0,
                            age: 0.0,
                            lifespan: adjusted_lifespan,
                            velocity_y: 1.0 / (velocity * state.rng.next_velocity_offset(MIN_VELOCITY_OFFSET, MAX_VELOCITY_OFFSET)),
                            velocity_x: state.rng.next_range(-0.5, 0.5), // Small horizontal drift
                            size: state.rng.next_range(min_particle_size, max_particle_size),
                            wobble_phase: state.rng.next_range(0.0, 2.0 * std::f32::consts::PI),
                            turbulence_phase: state.rng.next_range(0.0, 2.0 * std::f32::consts::PI),
                            initial_brightness: state.rng.next_range(0.8, 1.2), // Brightness variation
                        });
                    }
                }

                // Render particles with fire-like color progression
                for particle in particles.iter() {
                    if particle.age >= particle.lifespan { continue; }

                    let t = particle.age / particle.lifespan;
                    let height_factor = 1.0 - (particle.y / height as f32); // 0 at bottom, 1 at top

                    // Get fire-like color progression
                    let (h, s, v) = get_fire_color((h_base, s_base, v_base), t, height_factor);
                    let fire_rgb = hsv_to_rgb(h, s, v);

                    // Apply flickering brightness variation
                    let flicker = 1.0 + FLICKER_INTENSITY * (particle.turbulence_phase * 3.7).sin() * particle.initial_brightness;
                    let brightness_mult = flicker * (1.0 - t).powf(1.2); // Exponential fade with flicker

                    let rgb = [
                        ((fire_rgb[0] as f32 * brightness_mult).min(255.0).max(0.0)) as u8,
                        ((fire_rgb[1] as f32 * brightness_mult).min(255.0).max(0.0)) as u8,
                        ((fire_rgb[2] as f32 * brightness_mult).min(255.0).max(0.0)) as u8,
                    ];

                    // Enhanced wobble with more chaotic motion
                    let wobble_intensity = wobble * (1.0 + t * 0.5); // More wobble as particle ages
                    let x_disp = particle.x + wobble_intensity * (t * 12.0 + particle.wobble_phase).sin()
                                            + wobble_intensity * 0.3 * (t * 8.5 + particle.wobble_phase * 1.7).cos();

                    let y_scaled = (height as f32 - particle.y) * scale;
                    let y_render = height as f32 - y_scaled;

                    let xi = x_disp.round() as i32;
                    let yi = y_render.round() as i32;

                    // Size varies more dramatically - bigger at base, smaller at tips
                    let size_factor = (1.0 - t * 0.7) * (1.0 - height_factor * 0.3);
                    let final_size = particle.size * size_factor;
                    let size = final_size as i32;
                    let size_f = final_size;
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
        } // End of particle processing block

        // Apply blur (still without GIL)
        if blur_amount > 0 {
            simple_blur(&mut output, blur_amount);
        }
        }); // End of allow_threads block - GIL is reacquired here

        // STEP 3: Convert result back to Python object (requires GIL)
        Ok(PyArray3::from_owned_array_bound(py, output).into())
    })
}
