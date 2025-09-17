use rand::{Rng, SeedableRng};
use rand::rngs::SmallRng;
use rand::distributions::{Distribution, Uniform};
use std::collections::HashMap;

// Thread-local RNG for better performance and quality
thread_local! {
    static RNG: std::cell::RefCell<SmallRng> = std::cell::RefCell::new(SmallRng::from_entropy());
}

// High-quality random number generation utilities
pub struct SimpleRng;

impl SimpleRng {
    // Generate a random f32 in [0, 1)
    pub fn next_f32() -> f32 {
        RNG.with(|rng| rng.borrow_mut().gen())
    }

    // Generate a random f32 in [min, max)
    pub fn next_range(min: f32, max: f32) -> f32 {
        // Handle edge case where min >= max
        if min >= max {
            return min;
        }

        RNG.with(|rng| {
            let dist = Uniform::from(min..max);
            dist.sample(&mut *rng.borrow_mut())
        })
    }

    // Generate velocity with realistic triangular distribution
    pub fn next_velocity_offset(min: f32, max: f32) -> f32 {
        // Handle edge case where min >= max
        if min >= max {
            return min;
        }

        let r = Self::next_f32();
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

/// A simple particle representation for blob rendering.
pub struct Particle {
    pub x: f32,
    pub y: f32,
    pub color: [u8; 3],
    pub radius: usize,
    /// alpha in range [0.0, 1.0]
    pub alpha: f32,
}

/// Render particles as soft blobs into `output` using a single-threaded accumulator.
/// This avoids a global post-process blur by drawing a small kernel for each particle.
pub fn render_particle_blobs_singlethread(
    output: &mut ndarray::Array3<u8>,
    particles: &[Particle],
    additive: bool,
) {
    let (height, width, channels) = output.dim();
    if channels < 3 {
        // For simplicity we only handle RGB output here
        return;
    }

    // Accumulator with float precision
    let mut accum = ndarray::Array3::<f32>::zeros((height, width, 3));

    // Initialize accumulator from existing output if not additive=false
    if !additive {
        for y in 0..height {
            for x in 0..width {
                accum[(y, x, 0)] = output[(y, x, 0)] as f32;
                accum[(y, x, 1)] = output[(y, x, 1)] as f32;
                accum[(y, x, 2)] = output[(y, x, 2)] as f32;
            }
        }
    }

    // Kernel cache keyed by radius
    let mut kernel_cache: HashMap<usize, Vec<f32>> = HashMap::new();

    for p in particles {
        if p.alpha <= 0.0 || p.radius == 0 {
            continue;
        }

        let r = p.radius;
        let diameter = 2 * r + 1;

        // get or build kernel
        let kernel = kernel_cache.entry(r).or_insert_with(|| {
            let mut k = vec![0f32; diameter * diameter];
            // sigma chosen so kernel fits nicely within radius
            let sigma = (r as f32) * 0.5 + 0.5;
            let two_sigma_sq = 2.0 * sigma * sigma;
            let mut sum = 0f32;
            for ky in 0..diameter {
                for kx in 0..diameter {
                    let dx = kx as i32 - r as i32;
                    let dy = ky as i32 - r as i32;
                    let v = ( -((dx * dx + dy * dy) as f32) / two_sigma_sq ).exp();
                    k[ky * diameter + kx] = v;
                    sum += v;
                }
            }
            if sum > 0.0 {
                for val in &mut k {
                    *val /= sum;
                }
            }
            k
        });

        // precompute color components
        let cr = p.color[0] as f32;
        let cg = p.color[1] as f32;
        let cb = p.color[2] as f32;
        let alpha = p.alpha;

        // integer center
        let cx = p.x.round() as i32;
        let cy = p.y.round() as i32;

        let sx = (cx - r as i32).max(0) as usize;
        let ex = (cx + r as i32).min((width as i32) - 1) as usize;
        let sy = (cy - r as i32).max(0) as usize;
        let ey = (cy + r as i32).min((height as i32) - 1) as usize;

        for yy in sy..=ey {
            let ky = yy as i32 - (cy - r as i32);
            let row_base = (ky as usize) * diameter;
            for xx in sx..=ex {
                let kx = xx as i32 - (cx - r as i32);
                let kv = kernel[row_base + (kx as usize)];
                if kv <= 0.0 {
                    continue;
                }
                let add_r = kv * cr * alpha;
                let add_g = kv * cg * alpha;
                let add_b = kv * cb * alpha;
                accum[(yy, xx, 0)] += add_r;
                accum[(yy, xx, 1)] += add_g;
                accum[(yy, xx, 2)] += add_b;
            }
        }
    }

    // write back (clamp to 0..255)
    for y in 0..height {
        for x in 0..width {
            let vr = accum[(y, x, 0)].round().clamp(0.0, 255.0) as u8;
            let vg = accum[(y, x, 1)].round().clamp(0.0, 255.0) as u8;
            let vb = accum[(y, x, 2)].round().clamp(0.0, 255.0) as u8;
            output[(y, x, 0)] = vr;
            output[(y, x, 1)] = vg;
            output[(y, x, 2)] = vb;
        }
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blob_renderer_smoke() {
        let mut out = ndarray::Array3::<u8>::zeros((64, 64, 3));
        let particles = vec![Particle { x: 32.0, y: 32.0, color: [255, 100, 50], radius: 5, alpha: 1.0 }];
        render_particle_blobs_singlethread(&mut out, &particles, false);
        // ensure at least one pixel is non-zero
        let mut any_nonzero = false;
        for y in 0..64 {
            for x in 0..64 {
                if out[(y, x, 0)] != 0 || out[(y, x, 1)] != 0 || out[(y, x, 2)] != 0 {
                    any_nonzero = true;
                    break;
                }
            }
            if any_nonzero { break; }
        }
        assert!(any_nonzero, "blob renderer produced all-zero output");
    }
}
