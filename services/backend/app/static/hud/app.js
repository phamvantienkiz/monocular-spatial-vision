// Monocular Spatial Vision — Operator HUD Client Application
// Real-time telemetry via WebSocket, Artificial Horizon gauge, Optical Reticle, and BEV Radar.

const statusOrb = document.getElementById("orb-status");
const statusBadge = document.getElementById("hud-status");
const valPitch = document.getElementById("val-pitch");
const valRoll = document.getElementById("val-roll");
const valHeight = document.getElementById("val-height");
const valFps = document.getElementById("val-fps");
const valCamFps = document.getElementById("val-cam-fps");
const valFrameId = document.getElementById("val-frame-id");
const valStreamSource = document.getElementById("val-stream-source");
const objectList = document.getElementById("object-list");

// Canvases
const attitudeCanvas = document.getElementById("attitude-canvas");
const attCtx = attitudeCanvas.getContext("2d");

const bevCanvas = document.getElementById("bev-canvas");
const bevCtx = bevCanvas.getContext("2d");

const overlayCanvas = document.getElementById("hud-overlay-canvas");
const overlayCtx = overlayCanvas.getContext("2d");

let showOverlay = true;
let currentPitch = 12.5;
let currentRoll = 0.0;
let latestObjects = [];

// Toggle Optical Reticle Button
document.getElementById("btn-toggle-grid").addEventListener("click", () => {
  showOverlay = !showOverlay;
  if (!showOverlay) {
    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  }
});

// WebSocket Initialization
const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/telemetry`;
let ws;

function connectWebSocket() {
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    statusBadge.textContent = "CONNECTED (STANDBY)";
    statusBadge.className = "status-badge connecting";
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      updateTelemetry(data);
      drawAttitudeHorizon(data.pitch_deg || 0, data.roll_deg || 0);
      drawBEV(data.objects || []);
      if (showOverlay) {
        drawOpticalOverlay(data.pitch_deg || 12.5, data.roll_deg || 0);
      }
    } catch (err) {
      console.error("Error parsing telemetry WebSocket:", err);
    }
  };

  ws.onclose = () => {
    statusOrb.className = "status-orb";
    statusBadge.textContent = "DISCONNECTED";
    statusBadge.className = "status-badge connecting";
    valStreamSource.textContent = "OFFLINE";
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = () => {
    ws.close();
  };
}

function updateTelemetry(data) {
  currentPitch = data.pitch_deg;
  currentRoll = data.roll_deg;

  valPitch.textContent = `${data.pitch_deg >= 0 ? "+" : ""}${data.pitch_deg.toFixed(2)}°`;
  valRoll.textContent = `${data.roll_deg >= 0 ? "+" : ""}${data.roll_deg.toFixed(2)}°`;
  valHeight.textContent = `${data.camera_height_m.toFixed(3)} m`;
  valFps.textContent = `${data.fps.toFixed(1)} FPS`;
  valCamFps.textContent = `${data.fps.toFixed(1)}`;
  valFrameId.textContent = `#${data.frame_id}`;

  if (data.is_streaming) {
    statusOrb.className = "status-orb online";
    statusBadge.textContent = "STREAMING (LIVE)";
    statusBadge.className = "status-badge online";
    valStreamSource.textContent = "PI 3 TCP";
  } else {
    statusOrb.className = "status-orb";
    statusBadge.textContent = "INGEST STANDBY";
    statusBadge.className = "status-badge connecting";
    valStreamSource.textContent = "STANDBY";
  }

  latestObjects = data.objects || [];
  if (latestObjects.length > 0) {
    objectList.innerHTML = latestObjects
      .map(
        (obj) =>
          `<li><strong>#${obj.id} ${obj.class_name}</strong>: Z=${obj.distance_z.toFixed(2)}m | Pos=[${obj.pos_xyz.map((v) => v.toFixed(2)).join(", ")}]</li>`
      )
      .join("");
  } else {
    objectList.innerHTML = `<li class="empty-msg">Sensor acquisition active. 3D Detector pipeline activates in Release 2.</li>`;
  }
}

// 1. Draw Artificial Horizon Attitude Gauge
function drawAttitudeHorizon(pitchDeg, rollDeg) {
  const w = attitudeCanvas.width;
  const h = attitudeCanvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const radius = cx - 4;

  attCtx.clearRect(0, 0, w, h);

  // Clip to circular gauge
  attCtx.save();
  attCtx.beginPath();
  attCtx.arc(cx, cy, radius, 0, Math.PI * 2);
  attCtx.clip();

  // Rotate for Roll and Translate for Pitch
  attCtx.save();
  attCtx.translate(cx, cy);
  attCtx.rotate((-rollDeg * Math.PI) / 180);

  // Pitch translation (approx 3 pixels per degree)
  const pitchOffset = pitchDeg * 2.8;
  attCtx.translate(0, pitchOffset);

  // Sky (Top half)
  attCtx.fillStyle = "#0284c7"; // Sky blue
  attCtx.fillRect(-w, -h * 2, w * 2, h * 2);

  // Ground (Bottom half)
  attCtx.fillStyle = "#78350f"; // Earth amber/brown
  attCtx.fillRect(-w, 0, w * 2, h * 2);

  // Horizon Line
  attCtx.strokeStyle = "#f8fafc";
  attCtx.lineWidth = 2.5;
  attCtx.beginPath();
  attCtx.moveTo(-w, 0);
  attCtx.lineTo(w, 0);
  attCtx.stroke();

  // Pitch ladder markers (every 10 deg)
  attCtx.strokeStyle = "rgba(255, 255, 255, 0.7)";
  attCtx.fillStyle = "rgba(255, 255, 255, 0.85)";
  attCtx.font = "9px monospace";
  attCtx.textAlign = "center";

  for (let deg = -40; deg <= 40; deg += 10) {
    if (deg === 0) continue;
    const yPos = -deg * 2.8;
    const barWidth = deg % 20 === 0 ? 40 : 24;

    attCtx.beginPath();
    attCtx.moveTo(-barWidth / 2, yPos);
    attCtx.lineTo(barWidth / 2, yPos);
    attCtx.stroke();

    if (deg % 20 === 0) {
      attCtx.fillText(`${Math.abs(deg)}`, -barWidth / 2 - 12, yPos + 3);
      attCtx.fillText(`${Math.abs(deg)}`, barWidth / 2 + 12, yPos + 3);
    }
  }

  attCtx.restore();

  // Fixed aircraft / camera symbol at center
  attCtx.strokeStyle = "#facc15"; // Yellow reticle
  attCtx.lineWidth = 3;
  attCtx.beginPath();
  // Left wing
  attCtx.moveTo(cx - 36, cy);
  attCtx.lineTo(cx - 12, cy);
  attCtx.lineTo(cx - 12, cy + 6);
  // Center dot
  attCtx.moveTo(cx, cy - 2);
  attCtx.arc(cx, cy, 3, 0, Math.PI * 2);
  // Right wing
  attCtx.moveTo(cx + 12, cy + 6);
  attCtx.lineTo(cx + 12, cy);
  attCtx.lineTo(cx + 36, cy);
  attCtx.stroke();

  attCtx.restore();

  // Gauge border ring
  attCtx.strokeStyle = "#38bdf8";
  attCtx.lineWidth = 3;
  attCtx.beginPath();
  attCtx.arc(cx, cy, radius, 0, Math.PI * 2);
  attCtx.stroke();
}

// 2. Draw Optical Center Reticle & Horizon on Camera Feed
function drawOpticalOverlay(pitchDeg, rollDeg) {
  const w = overlayCanvas.width;
  const h = overlayCanvas.height;
  const cx = w / 2; // 640
  const cy = h / 2; // 360

  overlayCtx.clearRect(0, 0, w, h);

  // Optical Center Reticle
  overlayCtx.strokeStyle = "rgba(56, 189, 248, 0.4)";
  overlayCtx.lineWidth = 1;
  overlayCtx.setLineDash([6, 6]);

  overlayCtx.beginPath();
  overlayCtx.moveTo(cx, 0);
  overlayCtx.lineTo(cx, h);
  overlayCtx.moveTo(0, cy);
  overlayCtx.lineTo(w, cy);
  overlayCtx.stroke();
  overlayCtx.setLineDash([]);

  // Center crosshair
  overlayCtx.strokeStyle = "#06b6d4";
  overlayCtx.lineWidth = 2;
  overlayCtx.beginPath();
  overlayCtx.arc(cx, cy, 14, 0, Math.PI * 2);
  overlayCtx.moveTo(cx - 24, cy);
  overlayCtx.lineTo(cx - 14, cy);
  overlayCtx.moveTo(cx + 14, cy);
  overlayCtx.lineTo(cx + 24, cy);
  overlayCtx.moveTo(cx, cy - 24);
  overlayCtx.lineTo(cx, cy - 14);
  overlayCtx.moveTo(cx, cy + 14);
  overlayCtx.lineTo(cx, cy + 24);
  overlayCtx.stroke();

  // Dynamic ground plane line calculated from pitch
  const fy = 920.0;
  const pitchRad = (pitchDeg * Math.PI) / 180.0;
  const horizonV = cy - fy * Math.tan(pitchRad);

  if (horizonV >= 0 && horizonV <= h) {
    overlayCtx.strokeStyle = "rgba(244, 63, 94, 0.75)";
    overlayCtx.lineWidth = 2;
    overlayCtx.beginPath();
    overlayCtx.moveTo(40, horizonV);
    overlayCtx.lineTo(w - 40, horizonV);
    overlayCtx.stroke();

    overlayCtx.fillStyle = "rgba(244, 63, 94, 0.9)";
    overlayCtx.font = "12px monospace";
    overlayCtx.fillText(`GROUND HORIZON (θ=${pitchDeg.toFixed(1)}°)`, 50, horizonV - 8);
  }
}

// 3. Draw Bird's Eye View (BEV) Radar
function drawBEV(objects) {
  const w = bevCanvas.width;
  const h = bevCanvas.height;
  bevCtx.clearRect(0, 0, w, h);

  bevCtx.fillStyle = "#030712";
  bevCtx.fillRect(0, 0, w, h);

  const cx = w / 2;
  const bottomY = h - 25;
  const scale = 55; // 55 pixels per meter

  // Distance rings (1m, 2m, 3m, 4m, 5m)
  bevCtx.lineWidth = 1;
  for (let r = 1; r <= 5; r++) {
    bevCtx.strokeStyle = r === 3 ? "rgba(6, 182, 212, 0.4)" : "rgba(55, 65, 81, 0.5)";
    bevCtx.beginPath();
    bevCtx.arc(cx, bottomY, r * scale, Math.PI, 2 * Math.PI);
    bevCtx.stroke();

    bevCtx.fillStyle = "#64748b";
    bevCtx.font = "10px monospace";
    bevCtx.fillText(`${r}.0m`, cx + 6, bottomY - r * scale + 12);
  }

  // Camera Field-of-View (FOV) Cone (~68 deg horizontal)
  const fovAngle = (34 * Math.PI) / 180;
  const fovDist = 5 * scale;
  bevCtx.strokeStyle = "rgba(56, 189, 248, 0.25)";
  bevCtx.beginPath();
  bevCtx.moveTo(cx, bottomY);
  bevCtx.lineTo(cx - fovDist * Math.sin(fovAngle), bottomY - fovDist * Math.cos(fovAngle));
  bevCtx.moveTo(cx, bottomY);
  bevCtx.lineTo(cx + fovDist * Math.sin(fovAngle), bottomY - fovDist * Math.cos(fovAngle));
  bevCtx.stroke();

  // Camera origin triangle
  bevCtx.fillStyle = "#38bdf8";
  bevCtx.beginPath();
  bevCtx.moveTo(cx, bottomY - 10);
  bevCtx.lineTo(cx - 7, bottomY + 2);
  bevCtx.lineTo(cx + 7, bottomY + 2);
  bevCtx.closePath();
  bevCtx.fill();

  // Render objects if present
  objects.forEach((obj) => {
    const ox = cx + obj.pos_xyz[0] * scale;
    const oy = bottomY - obj.pos_xyz[2] * scale;

    bevCtx.fillStyle = "#ef4444";
    bevCtx.beginPath();
    bevCtx.arc(ox, oy, 6, 0, 2 * Math.PI);
    bevCtx.fill();

    bevCtx.fillStyle = "#f8fafc";
    bevCtx.font = "11px monospace";
    bevCtx.fillText(`${obj.class_name} (${obj.distance_z.toFixed(2)}m)`, ox + 8, oy - 2);
  });
}

// 4. Laser Benchmark Verification Form
document.getElementById("laser-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const laserVal = parseFloat(document.getElementById("laser-input").value);
  if (isNaN(laserVal) || laserVal <= 0) return;

  // Compute estimate: using latest object distance or IPM calculation based on nominal pitch
  const estVal = latestObjects.length > 0 ? latestObjects[0].distance_z : (0.285 / Math.tan((currentPitch * Math.PI) / 180));
  const absErr = Math.abs(estVal - laserVal);
  const absRel = (absErr / laserVal) * 100.0;
  const passed = absRel <= 5.0;

  document.getElementById("res-est").textContent = estVal.toFixed(3);
  document.getElementById("res-abs").textContent = absErr.toFixed(3);
  document.getElementById("res-absrel").textContent = absRel.toFixed(2);

  const badge = document.getElementById("res-badge");
  badge.textContent = passed ? "PASS (≤ 5.0% ERROR)" : "FAIL (> 5.0% ERROR)";
  badge.className = `badge-status ${passed ? "pass" : "fail"}`;
});

// Initial canvas renders
drawAttitudeHorizon(12.5, 0.0);
drawBEV([]);
drawOpticalOverlay(12.5, 0.0);

// Start WebSocket connection
connectWebSocket();
