//! One input and one solve per process; allocation telemetry never affects timing benchmarks.
use serde_json::json;
use std::{
    alloc::{GlobalAlloc, Layout, System},
    fs,
    sync::atomic::{AtomicUsize, Ordering::Relaxed},
    time::{Duration, Instant},
};
use table_stretch::{AblationOptions, Limits, NativeAlgorithm, Table, solve_ablation_with_timeout};

struct MeasuredAllocator {
    live: AtomicUsize,
    peak: AtomicUsize,
}

impl MeasuredAllocator {
    const fn new() -> Self {
        Self {
            live: AtomicUsize::new(0),
            peak: AtomicUsize::new(0),
        }
    }

    fn add(&self, size: usize) {
        let live = self.live.fetch_add(size, Relaxed) + size;
        self.peak.fetch_max(live, Relaxed);
    }

    // Called only with the single-threaded solver idle and its input already loaded.
    fn begin(&self) -> usize {
        let baseline = self.live.load(Relaxed);
        self.peak.store(baseline, Relaxed);
        baseline
    }
}

// SAFETY: every operation delegates to System with the original layout/pointer.
// Accounting uses only non-allocating atomics, never reads allocated memory,
// and updates realloc ownership only when System reports success.
unsafe impl GlobalAlloc for MeasuredAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let ptr = unsafe { System.alloc(layout) };
        if !ptr.is_null() {
            self.add(layout.size());
        }
        ptr
    }

    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        let ptr = unsafe { System.alloc_zeroed(layout) };
        if !ptr.is_null() {
            self.add(layout.size());
        }
        ptr
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) };
        self.live.fetch_sub(layout.size(), Relaxed);
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        let next = unsafe { System.realloc(ptr, layout, new_size) };
        if !next.is_null() {
            if new_size >= layout.size() {
                self.add(new_size - layout.size());
            } else {
                self.live.fetch_sub(layout.size() - new_size, Relaxed);
            }
        }
        next
    }
}

#[global_allocator]
static ALLOCATOR: MeasuredAllocator = MeasuredAllocator::new();

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let path = args.next().ok_or("expected table JSON path")?;
    let algorithm: NativeAlgorithm =
        serde_json::from_value(json!(args.next().ok_or("expected algorithm")?))?;
    let timeout_ms: u64 = args.next().ok_or("expected timeout in ms")?.parse()?;
    let options: AblationOptions = args
        .next()
        .map(|s| serde_json::from_str(&s))
        .transpose()?
        .unwrap_or_default();
    let table: Table = serde_json::from_slice(&fs::read(path)?)?;
    // The temporary JSON buffer has been dropped. Only this case is resident.
    let limits = Limits {
        max_generated: u64::MAX,
        max_comparisons: u64::MAX,
        max_frontier: usize::MAX,
    };
    let baseline = ALLOCATOR.begin();
    let start = Instant::now();
    let result = solve_ablation_with_timeout(
        &table,
        limits,
        algorithm,
        options,
        Some(Duration::from_millis(timeout_ms)),
    );
    let wall_ns = start.elapsed().as_nanos();
    let peak = ALLOCATOR.peak.load(Relaxed);
    let end = ALLOCATOR.live.load(Relaxed);
    // Capture counters before any output serialization; successful layout remains live.
    let (status, layout, error) = match result {
        Ok((layout, _)) => (
            if layout.optimal {
                "optimal"
            } else {
                "heuristic"
            },
            Some(layout),
            None,
        ),
        Err(error) => {
            let status = match &error {
                table_stretch::Error::Limit("wall time") => "timeout",
                table_stretch::Error::Limit(_) => "resource_limit",
                _ => "error",
            };
            (status, None, Some(error.to_string()))
        }
    };
    println!(
        "{}",
        json!({"status":status,"layout":layout,"error":error,"wall_ns":wall_ns,
        "heap_baseline_bytes":baseline,"heap_peak_bytes":peak,
        "heap_extra_peak_bytes":peak-baseline,"heap_end_bytes":end})
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn peak_counts_live_bytes_not_cumulative_traffic() {
        // A local instance isolates accounting from the parallel test harness.
        let a = MeasuredAllocator::new();
        let small = Layout::from_size_align(64, 8).unwrap();
        let large = Layout::from_size_align(256, 8).unwrap();
        unsafe {
            let input = a.alloc(small);
            assert!(!input.is_null());
            assert_eq!(a.begin(), 64);
            let p = a.alloc_zeroed(small);
            assert!(!p.is_null());
            assert_eq!(*p, 0);
            let p = a.realloc(p, small, 256);
            assert!(!p.is_null());
            assert_eq!(a.peak.load(Relaxed), 320);
            let p = a.realloc(p, large, 64);
            assert!(!p.is_null());
            assert_eq!(a.live.load(Relaxed), 128);
            a.dealloc(p, small);
            for _ in 0..10 {
                let p = a.alloc(small);
                assert!(!p.is_null());
                a.dealloc(p, small);
            }
            assert_eq!(a.peak.load(Relaxed), 320);
            assert_eq!(a.begin(), 64);
            assert_eq!(a.peak.load(Relaxed), 64);
            a.dealloc(input, small);
            assert_eq!(a.live.load(Relaxed), 0);
        }
    }
}
