use rand::{Rng, SeedableRng};
use rand::rngs::SmallRng;
use rand::distributions::{Distribution, Uniform};

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

// Simple blur function with proper edge handling
pub fn simple_blur(output: &mut ndarray::Array3<u8>, blur_amount: usize) {
    if blur_amount == 0 {
        return;
    }

    let (height, width, _) = output.dim();
    let mut temp = output.clone();

    // Helper function to get pixel with mirror padding for edges
    let get_pixel_mirrored = |arr: &ndarray::Array3<u8>, y: i32, x: i32, c: usize| -> u8 {
        let safe_y = if y < 0 {
            (-y) as usize
        } else if y >= height as i32 {
            height - 1 - ((y - height as i32) as usize)
        } else {
            y as usize
        }.min(height - 1);

        let safe_x = if x < 0 {
            (-x) as usize
        } else if x >= width as i32 {
            width - 1 - ((x - width as i32) as usize)
        } else {
            x as usize
        }.min(width - 1);

        arr[(safe_y, safe_x, c)]
    };

    for _ in 0..blur_amount {
        for y in 0..height {
            for x in 0..width {
                for c in 0..3 {
                    let y_i = y as i32;
                    let x_i = x as i32;

                    let sum = get_pixel_mirrored(output, y_i - 1, x_i - 1, c) as u16
                        + get_pixel_mirrored(output, y_i - 1, x_i, c) as u16
                        + get_pixel_mirrored(output, y_i - 1, x_i + 1, c) as u16
                        + get_pixel_mirrored(output, y_i, x_i - 1, c) as u16
                        + get_pixel_mirrored(output, y_i, x_i, c) as u16
                        + get_pixel_mirrored(output, y_i, x_i + 1, c) as u16
                        + get_pixel_mirrored(output, y_i + 1, x_i - 1, c) as u16
                        + get_pixel_mirrored(output, y_i + 1, x_i, c) as u16
                        + get_pixel_mirrored(output, y_i + 1, x_i + 1, c) as u16;
                    temp[(y, x, c)] = (sum / 9) as u8;
                }
            }
        }
        std::mem::swap(output, &mut temp);
    }
}
