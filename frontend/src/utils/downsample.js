/**
 * chart downsampling.
 *
 * A day of readings every 30 s is ~2,880 points squeezed into a few hundred pixels,
 * so the line turns into a smear. bucketSeries() groups readings into equal time
 * buckets (5 minutes) and returns 1 point per bucket:
 *   - mode "mean": average of the bucket (temperature, humidity, pH, ...)
 *   - mode "max":  highest value in the bucket (Air Quality: keep the worst score,
 *                  since averaging 1-4 scores gives meaningless values like 1.6)
 *
 * Points carry their real time (ms), so the chart can place them by time and show
 * gaps (the Pi was offline) instead of squeezing them out.
 *
 * Pure functions, no React: easy to test on their own.
 */

// Bucket sizes to choose from (minutes); the smallest that fits maxPoints wins
const NICE_MINUTES = [1, 2, 5, 10, 15, 30, 60, 120, 180, 360];
const MINUTE_MS = 60 * 1000;

/**
 * Pick a bucket size so the span produces at most `maxPoints` buckets.
 * Examples for 24 h of data:  maxPoints 300 -> 5 min (288 points),
 *                             maxPoints 720 -> 2 min (720 points)
 */
export function pickBucketMs(spanMs, maxPoints) {
    if (!(spanMs > 0) || !(maxPoints > 0)) return MINUTE_MS;
    const needed = spanMs / maxPoints;
    const minutes = NICE_MINUTES.find((m) => m * MINUTE_MS >= needed) ?? NICE_MINUTES[NICE_MINUTES.length - 1];
    return minutes * MINUTE_MS;
}

/**
 * @param values      numbers (already in display units)
 * @param times       epoch ms for each value (same length); NaN entries are skipped
 * @param bucketMs    bucket width in ms
 * @param mode        "mean" | "max"
 * @returns [{ t, value, start, count }] sorted by time
 *          t = average time of the readings in the bucket (where the point is drawn)
 *          start = bucket start (ms), count = readings in the bucket
 */
export function bucketSeries(values, times, bucketMs, mode = "mean") {
    const buckets = new Map();
    for (let i = 0; i < values.length; i++) {
        const v = values[i];
        const t = times[i];
        if (!Number.isFinite(v) || !Number.isFinite(t)) continue;
        const key = Math.floor(t / bucketMs);
        let b = buckets.get(key);
        if (!b) {
            b = { key, sum: 0, max: -Infinity, tSum: 0, count: 0 };
            buckets.set(key, b);
        }
        b.sum += v;
        b.max = Math.max(b.max, v);
        b.tSum += t;
        b.count += 1;
    }
    return [...buckets.values()]
        .sort((a, b) => a.key - b.key)
        .map((b) => ({
            t: b.tSum / b.count,
            start: b.key * bucketMs,
            value: mode === "max" ? b.max : b.sum / b.count,
            count: b.count,
        }));
}

/**
 * Split points into continuous segments, breaking wherever two neighbours are
 * further apart than `maxGapMs` (so the chart doesn't draw a line across a gap).
 */
export function splitAtGaps(points, maxGapMs) {
    const segments = [];
    let current = [];
    for (const p of points) {
        if (current.length && p.t - current[current.length - 1].t > maxGapMs) {
            segments.push(current);
            current = [];
        }
        current.push(p);
    }
    if (current.length) segments.push(current);
    return segments;
}