import React, { useMemo, useState } from "react";
import "../styles/sensorChart.css";
import { useTempUnit } from "../contexts/TempUnitContext.jsx";
import { toDisplayTemp, tempSymbol } from "../utils/units.js";
import { pickBucketMs, bucketSeries, splitAtGaps } from "../utils/downsample.js";   // NEW

// Suffix for non-temperature metrics; temperature comes from the context
const UNIT_LABEL = { humidity: "%", ph: "", pressure: " hPa", aqi_score: "" };

// NEW: the y-axis column is 42px wide, too narrow for "1013.3 hPa", so pressure
// axis labels show the number only (the unit is in the chart title, tooltip and footer)
const AXIS_HIDE_UNIT = new Set(["pressure"]);

// Chart vertical padding (in viewBox %)
const TOP_PADDING = 15;
const BOTTOM_PADDING = 15;
const USABLE_HEIGHT = 100 - TOP_PADDING - BOTTOM_PADDING;
const TICK_COUNT = 4; // 5 gridlines total

// NEW: x-axis time labels
const CHART_TIME_ZONE = "America/Los_Angeles";
const HOUR_MS = 60 * 60 * 1000;
// Roughly how many time labels to show in each view
const X_LABEL_TARGET = { collapsed: 4, expanded: 12 };
// Allowed spacing between labels (hours); smallest one that fits the target wins
const HOUR_STEPS = [1, 2, 3, 4, 6, 12, 24];

// downsampling. Draw at most this many points (one per time bucket):
// 24 h -> 5-min buckets collapsed (288 points), 2-min buckets expanded (720 points).
// Stats (average, min, max) still use every raw reading.

const MAX_POINTS = { collapsed: 400, expanded: 850 };
//  Air Quality is a 1-4 score: keep the WORST score per bucket and draw steps
// (averaging scores would give meaningless values like 1.6)
const STEP_METRICS = new Set(["aqi_score"]);
// break the line when readings are missing for more than this many buckets
// (e.g. the Pi was offline), instead of drawing a straight line across the gap
const GAP_BUCKETS = 3;

// Backend sends "YYYY-MM-DD HH:MM:SS" in UTC -> epoch ms
const parseUtc = (timestamp) =>
    timestamp ? new Date(timestamp.replace(" ", "T") + "Z").getTime() : NaN;

// Hour of day (0-23) in the chart's time zone, used to land labels on 12 AM, 6 AM, etc.
const hourFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: CHART_TIME_ZONE, hour: "2-digit", hourCycle: "h23",
});
const labelHourFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: CHART_TIME_ZONE, hour: "numeric",
});
const labelDateFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: CHART_TIME_ZONE, month: "short", day: "numeric",
});
//tooltip time for a bucket (epoch ms)
const tooltipTimeFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: CHART_TIME_ZONE, month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
});

function SensorChart({title, metric, data = [], timestamps = []}) {
    const { tempUnit } = useTempUnit();
    const [isExpanded, setIsExpanded] = useState(false);
    const [hoveredPoint, setHoveredPoint] = useState(null);

    const toggleExpand = () => {
        setIsExpanded((prev) => !prev);
    };

    const unit = metric === "temperature" ? tempSymbol(tempUnit) : UNIT_LABEL[metric] ?? "";
    const axisUnit = AXIS_HIDE_UNIT.has(metric) ? "" : unit;  

    // Trim float noise from conversion (82.49000000000001)
    const fmt = (n) => Number(n.toFixed(2));

    const isStep = STEP_METRICS.has(metric);   // NEW

    // split in two memos.
    //  1) raw: unit conversion + stats from EVERY reading (only when data/unit change)
    //  2) plot: downsampled points, lines, ticks (also when collapsed/expanded changes)
    // Hovering re-renders on every move, so neither is recomputed then.
    const raw = useMemo(() => {
        // Convert once, up front. The chart only displays, no threshold logic
        const values =
            metric === "temperature" ? data.map((c) => toDisplayTemp(c, tempUnit)) : data;
        const times = timestamps.map(parseUtc);

        const hasData = values.length > 0;
        // only fallback to 0/1 when there are no data at all.
        const maxValue = hasData ? Math.max(...values) : 1;
        const minValue = hasData ? Math.min(...values) : 0;
        // Average of ALL raw readings (already in the chosen unit), not the buckets
        const avgValue = hasData ? values.reduce((sum, v) => sum + v, 0) / values.length : null;

        const finiteTimes = times.filter(Number.isFinite);
        const tStart = finiteTimes.length ? Math.min(...finiteTimes) : 0;
        const tEnd = finiteTimes.length ? Math.max(...finiteTimes) : 0;

        return {
            values, times, hasData, minValue, maxValue, avgValue, tStart, tEnd,
            // time span the plotted data actually covers (oldest -> newest)
            rangeStart: timestamps[0],
            rangeEnd: timestamps[timestamps.length - 1],
        };
    }, [data, timestamps, metric, tempUnit]);

    const plot = useMemo(() => {
        const { values, times, minValue, maxValue, tStart, tEnd } = raw;
        const spanMs = tEnd - tStart;

        // one point per time bucket (average, or worst score for Air Quality)
        const bucketMs = pickBucketMs(spanMs, isExpanded ? MAX_POINTS.expanded : MAX_POINTS.collapsed);
        const buckets = bucketSeries(values, times, bucketMs, isStep ? "max" : "mean");

        // Y range: Air Quality uses whole-number ticks (1, 2, 3...); others the data range
        let yMin = minValue;
        let yMax = maxValue;
        if (isStep) {
            yMin = Math.floor(minValue);
            yMax = Math.max(Math.ceil(maxValue), yMin + 1);
        }
        const range = yMax - yMin || 1;
        // shared value -> y% mapping
        const getY = (value) => TOP_PADDING + (1 - (value - yMin) / range) * USABLE_HEIGHT;
        // x by TIME (not by index), so gaps show up where they really are
        const getX = (t) => (spanMs > 0 ? ((t - tStart) / spanMs) * 100 : 50);

        const points = buckets.map((b) => ({
            x: getX(b.t), y: getY(b.value), value: b.value, start: b.start, count: b.count,
        }));

        // one polyline per continuous segment; steps for Air Quality
        const lines = splitAtGaps(buckets, bucketMs * GAP_BUCKETS).map((seg) => {
            const pts = [];
            seg.forEach((b, i) => {
                const x = getX(b.t);
                const y = getY(b.value);
                if (isStep && i > 0) pts.push(`${x},${getY(seg[i - 1].value)}`);   // flat, then jump
                pts.push(`${x},${y}`);
            });
            return pts.join(" ");
        });

        // Y-axis ticks: Air Quality = whole numbers; others evenly spaced
        const tickValues = isStep
            ? Array.from({ length: yMax - yMin + 1 }, (_, i) => yMin + i)
            : Array.from({ length: TICK_COUNT + 1 }, (_, i) => yMin + (range * i) / TICK_COUNT);
        const ticks = tickValues.map((value) => ({ value: Math.round(value * 10) / 10, y: getY(value) }));

        // hour marks straight from the time range (exact, even across gaps).
        // LA is offset from UTC by whole hours, so whole UTC hours are whole local hours.
        const hourMarks = [];
        if (spanMs > 0) {
            for (let h = Math.ceil(tStart / HOUR_MS) * HOUR_MS; h <= tEnd; h += HOUR_MS) {
                const boundary = new Date(h);
                const localHour = Number(hourFormatter.format(boundary));
                hourMarks.push({
                    x: getX(h),
                    localHour,
                    // Midnight include  the date; other hours show "6 AM"
                    label: localHour === 0
                        ? labelDateFormatter.format(boundary)
                        : labelHourFormatter.format(boundary),
                });
            }
        }

        return { points, lines, ticks, hourMarks, spanHours: spanMs / HOUR_MS, bucketMinutes: bucketMs / 60000 };
    }, [raw, isExpanded, isStep]);

    const { hasData, minValue, maxValue, avgValue, rangeStart, rangeEnd } = raw;
    const { points, lines, ticks, hourMarks, spanHours, bucketMinutes } = plot;

    // pick which hour marks to label. Collapsed = few labels, expanded = more.
    // Step adapts to the data span, so 2h of data still gets labels, not just 24h.
    const xTicks = useMemo(() => {
        const target = isExpanded ? X_LABEL_TARGET.expanded : X_LABEL_TARGET.collapsed;
        const step = HOUR_STEPS.find((s) => spanHours / s <= target) ?? 24;
        return hourMarks.filter((m) => m.localHour % step === 0);
    }, [hourMarks, spanHours, isExpanded]);

    // points are placed by time now (not evenly), so find the point
    // nearest the cursor with a binary search on x.
    const handleMouseMove = (e) => {
        if (!points.length) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const xPct = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1) * 100;
        let lo = 0;
        let hi = points.length - 1;
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (points[mid].x < xPct) lo = mid + 1;
            else hi = mid;
        }
        const nearest = lo > 0 && xPct - points[lo - 1].x < points[lo].x - xPct ? lo - 1 : lo;
        // React skips the re-render when the index hasn't changed
        setHoveredPoint(nearest);
    };

    const handleMouseLeave = () => setHoveredPoint(null);

    // Format timestamp for display
    const formatTimestamp = (timestamp) => {
        if (!timestamp) return "";

        // Backend sends "YYYY-MM-DD HH:MM:SS" format in UTC
        // Convert to ISO format and append 'Z' to indicate UTC
        const utcTimestamp = timestamp.replace(' ', 'T') + 'Z';
        const date = new Date(utcTimestamp);

        return date.toLocaleString('en-US', {
            timeZone: 'America/Los_Angeles',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const hovered = hoveredPoint !== null ? points[hoveredPoint] : null;

    return (
        <div className={`sensor-chart-card ${isExpanded ? "expanded" : ""}`}
                onClick={toggleExpand}
        >
            <div className="sensor-chart-header">
                <h3>{title}</h3>
                <span className="expand-hint">
                    {isExpanded ? "Click to collapse" : "Click to expand"}
                </span>
            </div>

            {/* Row holding the summary panel (expanded only) + the chart */}
            <div className="sensor-chart-content">
                {/* Summary panel, hidden when collapsed */}
                {isExpanded && (
                    <aside className="chart-summary">
                        <div className="summary-avg">
                            {hasData ? `${fmt(avgValue)}${unit}` : "-"}
                        </div>
                        <div className="summary-label">Average · Last 24h</div>
                        {hasData && (
                            <div className="summary-range">
                                {formatTimestamp(rangeStart)} - {formatTimestamp(rangeEnd)}
                            </div>
                        )}
                        <div className="summary-minmax">
                            {hasData
                                ? `Min: ${fmt(minValue)}${unit} - Max: ${fmt(maxValue)}${unit}`
                                : "No data"}
                        </div>
                    </aside>
                )}

                <div className="sensor-chart-body">
                    {/* axis label column, rendered as HTML (not SVG) so text
                        doesn't get stretched by preserveAspectRatio="none" */}
                    <div className="chart-axis-labels">
                        {ticks.map((tick, i) => (
                            <span key={i} className="axis-label" style={{ top: `${tick.y}%` }}>
                                {tick.value}{axisUnit}
                            </span>
                        ))}
                    </div>

                    {/* mouse handlers live on the plot area itself, and the
                        tooltip is inside it, so dot, tooltip and cursor share the
                        same coordinate box  */}
                    <div
                        className="chart-plot-area"
                        onMouseMove={handleMouseMove}
                        onMouseLeave={handleMouseLeave}
                    >
                        <svg
                            viewBox="0 0 100 100"
                            preserveAspectRatio="none"
                            className="chart-svg"
                        >
                            {/* gridlines */}
                            {ticks.map((tick, i) => (
                                <line
                                    key={i}
                                    x1="0" y1={tick.y}
                                    x2="100" y2={tick.y}
                                    className="chart-gridline"
                                    vectorEffect="non-scaling-stroke"
                                />
                            ))}

                            {/*faint vertical gridline at each labeled hour */}
                            {xTicks.map((tick, i) => (
                                <line
                                    key={`x-${i}`}
                                    x1={tick.x} y1="0"
                                    x2={tick.x} y2="100"
                                    className="chart-gridline chart-gridline-x"
                                    vectorEffect="non-scaling-stroke"
                                />
                            ))}

                            {/* one line per continuous stretch of data (breaks at gaps).
                                Downsampled, so ~300 points instead of ~2,880. */}
                            {lines.map((pts, i) => (
                                <polyline
                                    key={i}
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                    strokeLinejoin="round"
                                    points={pts}
                                    vectorEffect="non-scaling-stroke"
                                />
                            ))}
                        </svg>

                        {/* x-axis time labels. Inside the plot area so their
                            x% lines up exactly with the data points. Edge labels are aligned inward */}
                        <div className="chart-x-labels">
                            {xTicks.map((tick, i) => (
                                <span
                                    key={i}
                                    className={`x-label ${
                                        tick.x < 4 ? "edge-left" : tick.x > 96 ? "edge-right" : ""
                                    } ${tick.localHour === 0 ? "x-label-day" : ""}`}
                                    style={{ left: `${tick.x}%` }}
                                >
                                    {tick.label}
                                </span>
                            ))}
                        </div>

                        {/* Hover dot: HTML so it stays a perfect circle at any chart size */}
                        {hovered && (
                            <span
                                className="chart-hover-dot"
                                style={{ left: `${hovered.x}%`, top: `${hovered.y}%` }}
                            />
                        )}

                        {/* Tooltip (moved inside the plot area) */}
                        {hovered && (
                            <div
                                className="chart-tooltip"
                                style={{ left: `${hovered.x}%`, top: `${hovered.y}%` }}
                            >
                                <div className="tooltip-value">
                                    {fmt(hovered.value)}{unit}
                                </div>
                                <div className="tooltip-timestamp">
                                    {tooltipTimeFormatter.format(new Date(hovered.start))}
                                </div>
                                {/* NEW: say what the point is, since it's a bucket, not one reading */}
                                <div className="tooltip-note">
                                    {isStep ? `Worst in ${bucketMinutes} min` : `${bucketMinutes}-min average`}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Collapsed view keeps the compact footer;
                expanded view shows Min/Max in the summary panel instead */}
            {!isExpanded && (
                <div className="sensor-chart-footer">
                    <span>Min: {fmt(minValue)}{unit}</span>
                    <span>Max: {fmt(maxValue)}{unit}</span>
                </div>
            )}
        </div>
    );
}

export default SensorChart;