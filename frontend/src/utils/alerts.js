/**
 * friendlier alert messages for display.
 *
 * The backend builds messages as "<sensor> <metric> is DANGER: ..." (data_collector.py),
 * e.g. "bme680 temperature is DANGER: ..." or "ph ph is WARNING: ...".
 * This rewrites only that leading part:
 *   "bme680 temperature is DANGER: 21.9 °C ..." -> "Temperature (BME680) is DANGER: 21.9 C ..."
 *   "ph ph is WARNING: 5.7 ..."                 -> "pH is WARNING: 5.7 ..."
 *   "bme280 humidity back to normal: 55%"       -> "Humidity (BME280) back to normal: 55%"
 * Anything that doesn't match is shown unchanged.
 */
const METRIC_LABEL = {
    temperature: "Temperature",
    humidity: "Humidity",
    ph: "pH",
    pressure: "Air Pressure",
    aqi_score: "Air Quality",
};

export function formatAlertMessage(message) {
    if (!message) return "";
    const m = /^(\w+) (\w+) (is |back to )/.exec(message);
    if (!m) return message;
    const [whole, sensor, metric, verb] = m;
    const label = METRIC_LABEL[metric] ?? metric;
    
    // pH is its own sensor, so "pH (PH)" would be redundant
    const who = sensor.toLowerCase() === metric.toLowerCase() ? label : `${label} (${sensor.toUpperCase()})`;
    return `${who} ${verb}${message.slice(whole.length)}`;
}