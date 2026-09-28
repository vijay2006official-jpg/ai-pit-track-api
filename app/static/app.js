document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();

  // Initialize Leaflet Map
  const map = L.map("map").setView([37.7749, -122.4194], 14);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap"
  }).addTo(map);

  let markersLayer = L.layerGroup().addTo(map);

  // Tabs
  const tabBtnPhoto = document.getElementById("tab-btn-photo");
  const tabBtnLive = document.getElementById("tab-btn-live");
  const tabContentPhoto = document.getElementById("tab-content-photo");
  const tabContentLive = document.getElementById("tab-content-live");

  tabBtnLive.addEventListener("click", () => {
    tabBtnLive.className = "px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-red-600 text-white transition-all flex items-center gap-1.5 shadow-md shadow-red-500/20";
    tabBtnPhoto.className = "px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-300 hover:text-white transition-all flex items-center gap-1.5";
    tabContentLive.classList.remove("hidden");
    tabContentPhoto.classList.add("hidden");
  });

  tabBtnPhoto.addEventListener("click", () => {
    tabBtnPhoto.className = "px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-amber-500 text-slate-950 transition-all flex items-center gap-1.5";
    tabBtnLive.className = "px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 text-slate-300 hover:text-white transition-all flex items-center gap-1.5";
    tabContentPhoto.classList.remove("hidden");
    tabContentLive.classList.add("hidden");
  });

  // DOM Elements
  const dropzone = document.getElementById("dropzone");
  const imageInput = document.getElementById("image-input");
  const dropzonePrompt = document.getElementById("dropzone-prompt");
  const imagePreview = document.getElementById("image-preview");
  const detectForm = document.getElementById("detect-form");
  const btnDetect = document.getElementById("btn-detect");
  const detectionResult = document.getElementById("detection-result");
  const resultImage = document.getElementById("result-image");
  const resultBadge = document.getElementById("result-badge");
  const detectionDetails = document.getElementById("detection-details");
  const btnUseLocation = document.getElementById("btn-use-location");
  const btnSamplePit = document.getElementById("btn-sample-pit");
  const btnRefreshMap = document.getElementById("btn-refresh-map");
  const pitsTableBody = document.getElementById("pits-table-body");
  const filterSeverity = document.getElementById("filter-severity");

  // KPI elements
  const statHealthIndex = document.getElementById("stat-health-index");
  const statActivePits = document.getElementById("stat-active-pits");
  const statCriticalPits = document.getElementById("stat-critical-pits");
  const statRepairedPits = document.getElementById("stat-repaired-pits");

  // Live Camera Elements
  const btnToggleCamera = document.getElementById("btn-toggle-camera");
  const btnPlaySimulatedVideo = document.getElementById("btn-play-simulated-video");
  const liveVideo = document.getElementById("live-video");
  const liveCanvas = document.getElementById("live-canvas");
  const livePlaceholder = document.getElementById("live-placeholder");
  const liveStatsOverlay = document.getElementById("live-stats-overlay");
  const liveFpsVal = document.getElementById("live-fps-val");
  const liveLatencyVal = document.getElementById("live-latency-val");
  const livePitsVal = document.getElementById("live-pits-val");
  const threatAlertBanner = document.getElementById("threat-alert-banner");
  const threatAlertText = document.getElementById("threat-alert-text");
  const cameraDeviceSelect = document.getElementById("camera-device-select");
  const liveGpsCoords = document.getElementById("live-gps-coords");
  const chkAudioAlert = document.getElementById("chk-audio-alert");

  let selectedFile = null;
  let mediaStream = null;
  let socket = null;
  let streamInterval = null;
  let simulationInterval = null;
  let isStreaming = false;
  let currentLat = 37.7749;
  let currentLon = -122.4194;
  let audioCtx = null;
  let lastAudioTime = 0;

  // Web Audio Hazard Warning Beeper
  function playAudioWarningBeep() {
    if (!chkAudioAlert.checked) return;
    const now = Date.now();
    if (now - lastAudioTime < 1800) return; // Debounce audio beeps
    lastAudioTime = now;

    try {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(880, audioCtx.currentTime); // High pitch warning
      osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.25);

      gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.25);

      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.25);
    } catch (e) {
      console.warn("Audio alert error:", e);
    }
  }

  // Live GPS Tracking Watcher
  if (navigator.geolocation) {
    navigator.geolocation.watchPosition(
      (pos) => {
        currentLat = pos.coords.latitude;
        currentLon = pos.coords.longitude;
        liveGpsCoords.textContent = `${currentLat.toFixed(4)}, ${currentLon.toFixed(4)}`;
      },
      () => {
        liveGpsCoords.textContent = "Lat: 37.7749, Lon: -122.4194";
      },
      { enableHighAccuracy: true, maximumAge: 5000 }
    );
  }

  // File Upload Elements
  const previewContainer = document.getElementById("preview-container");
  const fileNameLabel = document.getElementById("file-name-label");
  const btnClearImage = document.getElementById("btn-clear-image");

  dropzone.addEventListener("click", (e) => {
    if (e.target !== btnClearImage) {
      imageInput.click();
    }
  });

  imageInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  });

  btnClearImage.addEventListener("click", (e) => {
    e.stopPropagation();
    clearSelectedFile();
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("border-amber-500");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("border-amber-500");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("border-amber-500");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  });

  function handleFile(file) {
    if (!file || !file.type.startsWith("image/")) {
      alert("Please upload a valid road image file (.jpg, .png, .webp).");
      return;
    }
    selectedFile = file;
    fileNameLabel.textContent = `📄 ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;

    const reader = new FileReader();
    reader.onload = (e) => {
      imagePreview.src = e.target.result;
      previewContainer.classList.remove("hidden");
      dropzonePrompt.classList.add("hidden");
    };
    reader.readAsDataURL(file);
  }

  function clearSelectedFile() {
    selectedFile = null;
    imageInput.value = "";
    imagePreview.src = "";
    fileNameLabel.textContent = "";
    previewContainer.classList.add("hidden");
    dropzonePrompt.classList.remove("hidden");
    detectionResult.classList.add("hidden");
  }

  btnUseLocation.addEventListener("click", () => {
    document.getElementById("input-lat").value = currentLat.toFixed(5);
    document.getElementById("input-lon").value = currentLon.toFixed(5);
    map.setView([currentLat, currentLon], 15);
  });

  // Synthesize Test Pothole
  btnSamplePit.addEventListener("click", () => {
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext("2d");

    ctx.fillStyle = "#3b3f46";
    ctx.fillRect(0, 0, 640, 480);

    for (let i = 0; i < 20000; i++) {
      ctx.fillStyle = Math.random() > 0.5 ? "#2d3138" : "#4a4f58";
      ctx.fillRect(Math.random() * 640, Math.random() * 480, 2, 2);
    }

    ctx.fillStyle = "#fcd34d";
    ctx.fillRect(315, 0, 10, 100);
    ctx.fillRect(315, 160, 10, 100);
    ctx.fillRect(315, 320, 10, 100);

    ctx.fillStyle = "#15181e";
    ctx.beginPath();
    ctx.ellipse(320, 310, 85, 45, Math.PI / 16, 0, 2 * Math.PI);
    ctx.fill();

    ctx.fillStyle = "#0c0e12";
    ctx.beginPath();
    ctx.ellipse(315, 312, 60, 30, 0, 0, 2 * Math.PI);
    ctx.fill();

    canvas.toBlob((blob) => {
      const sampleFile = new File([blob], "sample_pothole.jpg", { type: "image/jpeg" });
      handleFile(sampleFile);
    }, "image/jpeg");
  });

  // Photo form submit
  detectForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!selectedFile) {
      alert("Please select or drop an image first, or click 'Load Test Pothole'.");
      return;
    }

    const lat = document.getElementById("input-lat").value;
    const lon = document.getElementById("input-lon").value;

    const formData = new FormData();
    formData.append("file", selectedFile);
    if (lat) formData.append("latitude", lat);
    if (lon) formData.append("longitude", lon);

    btnDetect.disabled = true;
    btnDetect.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Running Vision Model...`;
    lucide.createIcons();

    try {
      const res = await fetch("/api/v1/detect/image", {
        method: "POST",
        body: formData
      });
      const data = await res.json();

      if (data.success) {
        displayDetectionResult(data);
        fetchAnalytics();
        fetchPits();
      } else {
        alert("Detection returned error: " + (data.detail || "Unknown error"));
      }
    } catch (err) {
      alert("Request failed: " + err.message);
    } finally {
      btnDetect.disabled = false;
      btnDetect.innerHTML = `<i data-lucide="play" class="w-4 h-4"></i> Run AI Pit Detection`;
      lucide.createIcons();
    }
  });

  function displayDetectionResult(data) {
    detectionResult.classList.remove("hidden");
    resultImage.src = data.annotated_image_url;

    resultBadge.className = `text-xs px-2.5 py-0.5 rounded-full font-bold badge-${data.max_severity}`;
    resultBadge.textContent = `${data.total_pits_detected} DEFECT(S) • ${data.max_severity}`;

    let detailsHtml = `
      <div class="bg-slate-950 p-3 rounded-lg border border-slate-800">
        <p class="font-medium text-slate-200">${data.message}</p>
        <p class="text-slate-400 mt-1">Associated Pit ID: <span class="text-amber-400 font-semibold">${data.associated_pit_id || "N/A"}</span></p>
      </div>
    `;

    if (data.detections && data.detections.length > 0) {
      detailsHtml += `<div class="space-y-1.5 mt-2">`;
      data.detections.forEach((d) => {
        detailsHtml += `
          <div class="flex items-center justify-between p-2 rounded bg-slate-950/60 border border-slate-800/80">
            <span>Road Pit Defect #${d.id}</span>
            <span class="text-xs px-2 py-0.5 rounded badge-${d.severity}">${d.severity} (${(d.confidence * 100).toFixed(0)}%)</span>
          </div>
        `;
      });
      detailsHtml += `</div>`;
    }

    detectionDetails.innerHTML = detailsHtml;
  }

  // ==========================================
  // REAL-TIME WEBSOCKET LIVE CAMERA & VIDEO
  // ==========================================
  btnToggleCamera.addEventListener("click", () => {
    if (!isStreaming) {
      startLiveCamera();
    } else {
      stopLiveStream();
    }
  });

  btnPlaySimulatedVideo.addEventListener("click", () => {
    if (!isStreaming) {
      startSimulatedRoadVideo();
    } else {
      stopLiveStream();
    }
  });

  function connectWebSocket(onReadyCallback) {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${wsProtocol}//${window.location.host}/api/v1/detect/ws/stream`);

    socket.onopen = () => {
      isStreaming = true;
      livePlaceholder.classList.add("hidden");
      liveStatsOverlay.classList.remove("hidden");
      if (onReadyCallback) onReadyCallback();
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.success) {
        liveFpsVal.textContent = data.fps;
        liveLatencyVal.textContent = `${data.latency_ms}ms`;
        livePitsVal.textContent = data.total_pits_detected;

        drawBoundingBoxes(data.detections);

        if (data.total_pits_detected > 0) {
          threatAlertBanner.classList.remove("hidden");
          threatAlertText.textContent = `ALERT: ${data.total_pits_detected} ${data.max_severity} DEFECT(S) IN ROAD PATH!`;
          playAudioWarningBeep();
          fetchAnalytics();
          fetchPits();
        } else {
          threatAlertBanner.classList.add("hidden");
        }
      }
    };

    socket.onclose = () => stopLiveStream();
    socket.onerror = () => stopLiveStream();
  }

  async function startLiveCamera() {
    try {
      const facing = cameraDeviceSelect.value;
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: facing }
      });

      liveVideo.srcObject = mediaStream;
      liveVideo.classList.remove("hidden");

      connectWebSocket(() => {
        btnToggleCamera.className = "flex-1 bg-slate-800 hover:bg-slate-700 text-red-400 font-bold py-3 rounded-xl transition-all border border-red-500/30 flex items-center justify-center gap-2 text-sm";
        btnToggleCamera.innerHTML = `<i data-lucide="square" class="w-4 h-4"></i> Stop Live Camera`;
        lucide.createIcons();

        const offCanvas = document.createElement("canvas");
        const offCtx = offCanvas.getContext("2d");

        streamInterval = setInterval(() => {
          if (!socket || socket.readyState !== WebSocket.OPEN) return;
          if (liveVideo.videoWidth === 0) return;

          offCanvas.width = 480;
          offCanvas.height = 360;
          offCtx.drawImage(liveVideo, 0, 0, 480, 360);

          const frameBase64 = offCanvas.toDataURL("image/jpeg", 0.65);
          socket.send(JSON.stringify({
            image: frameBase64,
            latitude: currentLat,
            longitude: currentLon
          }));
        }, 70); // ~15 FPS
      });
    } catch (err) {
      alert("Cannot open camera. " + err.message + "\nTip: If testing on desktop without webcam, click 'Play Demo Video'!");
      stopLiveStream();
    }
  }

  // Simulated Road Driving Video Generator for Desktop testing
  function startSimulatedRoadVideo() {
    liveVideo.classList.add("hidden");
    const simCanvas = document.createElement("canvas");
    simCanvas.width = 480;
    simCanvas.height = 360;
    const simCtx = simCanvas.getContext("2d");

    let roadOffset = 0;
    let pitPosY = 0;

    connectWebSocket(() => {
      btnPlaySimulatedVideo.className = "px-4 bg-red-600 text-white font-semibold py-3 rounded-xl transition-colors flex items-center gap-1.5 text-xs";
      btnPlaySimulatedVideo.innerHTML = `<i data-lucide="square" class="w-4 h-4"></i> Stop Video`;
      lucide.createIcons();

      simulationInterval = setInterval(() => {
        roadOffset = (roadOffset + 12) % 60;
        pitPosY = (pitPosY + 6) % 360;

        // Draw moving road asphalt
        simCtx.fillStyle = "#33373d";
        simCtx.fillRect(0, 0, 480, 360);

        // Asphalt texture
        simCtx.fillStyle = "#282c32";
        for (let i = 0; i < 400; i++) {
          simCtx.fillRect((i * 47) % 480, (i * 31 + roadOffset) % 360, 2, 2);
        }

        // Center dashed yellow lane
        simCtx.fillStyle = "#f59e0b";
        for (let y = -60 + roadOffset; y < 360; y += 70) {
          simCtx.fillRect(236, y, 8, 45);
        }

        // Pothole in lane
        if (pitPosY > 80 && pitPosY < 320) {
          simCtx.fillStyle = "#111419";
          simCtx.beginPath();
          simCtx.ellipse(330, pitPosY, 50, 26, 0, 0, 2 * Math.PI);
          simCtx.fill();

          simCtx.fillStyle = "#080a0d";
          simCtx.beginPath();
          simCtx.ellipse(325, pitPosY + 2, 32, 16, 0, 0, 2 * Math.PI);
          simCtx.fill();
        }

        if (socket && socket.readyState === WebSocket.OPEN) {
          const frameBase64 = simCanvas.toDataURL("image/jpeg", 0.65);
          socket.send(JSON.stringify({
            image: frameBase64,
            latitude: currentLat,
            longitude: currentLon
          }));
        }
      }, 70);
    });
  }

  function stopLiveStream() {
    isStreaming = false;
    if (streamInterval) clearInterval(streamInterval);
    if (simulationInterval) clearInterval(simulationInterval);
    if (socket) socket.close();
    if (mediaStream) {
      mediaStream.getTracks().forEach(t => t.stop());
    }

    liveVideo.classList.add("hidden");
    livePlaceholder.classList.remove("hidden");
    liveStatsOverlay.classList.add("hidden");
    threatAlertBanner.classList.add("hidden");

    const ctx = liveCanvas.getContext("2d");
    ctx.clearRect(0, 0, liveCanvas.width, liveCanvas.height);

    btnToggleCamera.className = "flex-1 bg-gradient-to-r from-red-600 to-amber-600 hover:from-red-500 hover:to-amber-500 text-white font-bold py-3 rounded-xl transition-all shadow-md shadow-red-500/20 flex items-center justify-center gap-2 text-sm";
    btnToggleCamera.innerHTML = `<i data-lucide="camera" class="w-4 h-4"></i> Turn On Live Camera`;

    btnPlaySimulatedVideo.className = "px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold py-3 rounded-xl transition-colors border border-slate-700 flex items-center gap-1.5 text-xs";
    btnPlaySimulatedVideo.innerHTML = `<i data-lucide="film" class="w-4 h-4 text-amber-400"></i> Play Demo Video`;

    lucide.createIcons();
  }

  function drawBoundingBoxes(detections) {
    liveCanvas.width = liveCanvas.clientWidth;
    liveCanvas.height = liveCanvas.clientHeight;
    const ctx = liveCanvas.getContext("2d");
    ctx.clearRect(0, 0, liveCanvas.width, liveCanvas.height);

    const w = liveCanvas.width;
    const h = liveCanvas.height;

    const colors = {
      CRITICAL: "#ef4444",
      HIGH: "#f97316",
      MEDIUM: "#f59e0b",
      LOW: "#10b981"
    };

    detections.forEach((d) => {
      const x = d.bbox.x_min * w;
      const y = d.bbox.y_min * h;
      const bw = (d.bbox.x_max - d.bbox.x_min) * w;
      const bh = (d.bbox.y_max - d.bbox.y_min) * h;
      const color = colors[d.severity] || "#f59e0b";

      ctx.strokeStyle = color;
      ctx.lineWidth = 3.5;
      ctx.strokeRect(x, y, bw, bh);

      // Label background
      const text = `ROAD PIT #${d.id} | ${d.severity} ${(d.confidence * 100).toFixed(0)}%`;
      ctx.fillStyle = color;
      ctx.fillRect(x, Math.max(0, y - 22), ctx.measureText(text).width + 16, 22);

      ctx.fillStyle = "#000000";
      ctx.font = "bold 12px sans-serif";
      ctx.fillText(text, x + 6, Math.max(16, y - 6));
    });
  }

  // ==========================================
  // FETCH ANALYTICS & PITS
  // ==========================================
  async function fetchAnalytics() {
    try {
      const res = await fetch("/api/v1/analytics/summary");
      const summary = await res.json();

      statHealthIndex.textContent = summary.road_health_index_score;
      statActivePits.textContent = summary.active_pits;
      statCriticalPits.textContent = summary.severity_breakdown["CRITICAL"] || 0;
      statRepairedPits.textContent = summary.repaired_pits;
    } catch (e) {
      console.error("Failed to load analytics:", e);
    }
  }

  async function fetchPits() {
    const sev = filterSeverity.value;
    let url = "/api/v1/pits";
    if (sev) url += `?severity=${sev}`;

    try {
      const res = await fetch(url);
      const pits = await res.json();

      renderPitsTable(pits);
      renderMapMarkers(pits);
    } catch (e) {
      console.error("Failed to fetch pits:", e);
    }
  }

  function renderPitsTable(pits) {
    if (pits.length === 0) {
      pitsTableBody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-slate-500">No road pits registered yet. Turn on camera or upload photo.</td></tr>`;
      return;
    }

    pitsTableBody.innerHTML = pits.map(p => `
      <tr class="hover:bg-slate-900/50 transition-colors">
        <td class="px-3 py-3 font-semibold text-amber-400">#${p.id}</td>
        <td class="px-3 py-3 font-mono text-[11px] text-slate-400">${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}</td>
        <td class="px-3 py-3">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold badge-${p.severity}">${p.severity}</span>
        </td>
        <td class="px-3 py-3">
          <span class="px-2 py-0.5 rounded text-[10px] font-semibold badge-${p.status}">${p.status}</span>
        </td>
        <td class="px-3 py-3 space-x-1.5 flex items-center">
          <a href="/api/v1/reports/work-order/${p.id}" target="_blank" class="px-2 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-400 rounded text-[10px] border border-amber-500/30 font-medium flex items-center gap-1">
            <span>Work Order</span>
          </a>
          ${p.status !== 'REPAIRED' ? `
            <button onclick="updateStatus(${p.id}, 'REPAIRED')" class="px-2 py-1 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 rounded text-[10px] border border-emerald-500/30">
              Mark Repaired
            </button>
          ` : `
            <span class="text-[10px] text-slate-500">Fixed</span>
          `}
        </td>
      </tr>
    `).join("");
  }

  function renderMapMarkers(pits) {
    markersLayer.clearLayers();
    if (pits.length === 0) return;

    const bounds = [];
    pits.forEach(p => {
      const colorMap = {
        CRITICAL: "#ef4444",
        HIGH: "#f97316",
        MEDIUM: "#f59e0b",
        LOW: "#10b981"
      };

      const markerColor = colorMap[p.severity] || "#f59e0b";

      const circle = L.circleMarker([p.latitude, p.longitude], {
        radius: 8,
        fillColor: markerColor,
        color: "#ffffff",
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.85
      });

      const popupContent = `
        <div class="p-1 space-y-1">
          <div class="font-bold text-amber-400">Road Pit #${p.id}</div>
          <div class="text-xs">Severity: <span class="font-semibold" style="color:${markerColor}">${p.severity}</span></div>
          <div class="text-xs">Status: ${p.status}</div>
          <div class="text-[11px] text-slate-400">Detections: ${p.detection_count} times</div>
          ${p.latest_annotated_image ? `<img src="${p.latest_annotated_image}" class="w-full h-24 object-cover rounded mt-1 border border-slate-700"/>` : ''}
        </div>
      `;

      circle.bindPopup(popupContent);
      markersLayer.addLayer(circle);
      bounds.push([p.latitude, p.longitude]);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
  }

  // Status Updater
  window.updateStatus = async (pitId, newStatus) => {
    try {
      const res = await fetch(`/api/v1/pits/${pitId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus })
      });
      if (res.ok) {
        fetchAnalytics();
        fetchPits();
      }
    } catch (err) {
      alert("Failed to update pit status: " + err.message);
    }
  };

  filterSeverity.addEventListener("change", fetchPits);
  btnRefreshMap.addEventListener("click", () => {
    fetchAnalytics();
    fetchPits();
  });

  // Initial load
  fetchAnalytics();
  fetchPits();
});
