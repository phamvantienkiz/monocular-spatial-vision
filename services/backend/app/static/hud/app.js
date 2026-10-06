// Client-side JavaScript for Operator HUD
// Connects WebSocket, renders BEV canvas, and handles laser benchmark submissions.

const statusBadge = document.getElementById("hud-status");
const valPitch = document.getElementById("val-pitch");
const valRoll = document.getElementById("val-roll");
const valHeight = document.getElementById("val-height");
const valFps = document.getElementById("val-fps");
const objectList = document.getElementById("object-list");
const bevCanvas = document.getElementById("bev-canvas");
const ctx = bevCanvas.getContext("2d");

let latestObjects = [];

// Initialize WebSocket connection
const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/telemetry`;
let ws;

function connectWebSocket() {
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    statusBadge.textContent = "STATUS: ONLINE";
    statusBadge.classList.add("online");
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      updateTelemetry(data);
      renderBEV(data.objects || []);
    } catch (err) {
      console.error("Error parsing telemetry WebSocket:", err);
    }
  };

  ws.onclose = () => {
    statusBadge.textContent = "STATUS: RECONNECTING...";
    statusBadge.classList.remove("online");
    setTimeout(connectWebSocket, 2000);
  };
}

function updateTelemetry(data) {
  valPitch.textContent = `${data.pitch_deg.toFixed(2)}°`;
  valRoll.textContent = `${data.roll_deg.toFixed(2)}°`;
  valHeight.textContent = `${data.camera_height_m.toFixed(3)} m`;
  valFps.textContent = `${data.fps.toFixed(1)}`;

  latestObjects = data.objects || [];
  if (latestObjects.length > 0) {
    objectList.innerHTML = latestObjects
      .map(
        (obj) =>
          `<li><strong>#${obj.id} ${obj.class_name}</strong>: Z=${obj.distance_z.toFixed(2)}m | Pos=(${obj.pos_xyz.map((v) => v.toFixed(2)).join(", ")})</li>`
      )
      .join("");
  } else {
    objectList.innerHTML = `<li class="empty-msg">No objects detected</li>`;
  }
}

function renderBEV(objects) {
  ctx.fillStyle = "#111827";
  ctx.fillRect(0, 0, bevCanvas.width, bevCanvas.height);

  const cx = bevCanvas.width / 2;
  const bottomY = bevCanvas.height - 20;
  const scale = 50; // 50 pixels per meter

  // Draw grid distance rings (1m, 2m, 3m, 4m)
  ctx.strokeStyle = "#374151";
  ctx.lineWidth = 1;
  for (let r = 1; r <= 5; r++) {
    ctx.beginPath();
    ctx.arc(cx, bottomY, r * scale, Math.PI, 2 * Math.PI);
    ctx.stroke();
    ctx.fillStyle = "#6B7280";
    ctx.font = "10px sans-serif";
    ctx.fillText(`${r}m`, cx + 5, bottomY - r * scale + 12);
  }

  // Draw camera position
  ctx.fillStyle = "#3B82F6";
  ctx.beginPath();
  ctx.arc(cx, bottomY, 6, 0, 2 * Math.PI);
  ctx.fill();

  // Draw detected objects
  objects.forEach((obj) => {
    const ox = cx + obj.pos_xyz[0] * scale;
    const oy = bottomY - obj.pos_xyz[2] * scale;

    ctx.fillStyle = "#EF4444";
    ctx.beginPath();
    ctx.arc(ox, oy, 5, 0, 2 * Math.PI);
    ctx.fill();

    ctx.fillStyle = "#F9FAFB";
    ctx.font = "11px sans-serif";
    ctx.fillText(`${obj.class_name} (${obj.distance_z.toFixed(2)}m)`, ox + 7, oy - 2);
  });
}

// Laser benchmark verification form
document.getElementById("laser-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const laserVal = parseFloat(document.getElementById("laser-input").value);
  if (isNaN(laserVal) || latestObjects.length === 0) return;

  const targetObj = latestObjects[0];
  const estVal = targetObj.distance_z;
  const absErr = Math.abs(estVal - laserVal);
  const absRel = (absErr / laserVal) * 100.0;
  const passed = absRel <= 5.0;

  document.getElementById("res-est").textContent = estVal.toFixed(3);
  document.getElementById("res-abs").textContent = absErr.toFixed(3);
  document.getElementById("res-absrel").textContent = absRel.toFixed(2);

  const badge = document.getElementById("res-badge");
  badge.textContent = passed ? "PASS (≤ 5%)" : "FAIL (> 5%)";
  badge.className = `badge ${passed ? "pass" : "fail"}`;
});

// Start connection on load
connectWebSocket();
