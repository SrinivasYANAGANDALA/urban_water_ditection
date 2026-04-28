const uploadForm = document.getElementById("uploadForm");
const sampleBtn = document.getElementById("sampleBtn");
const statusMessage = document.getElementById("statusMessage");
const modeInfo = document.getElementById("modeInfo");
const alertsList = document.getElementById("alertsList");
const metricsGrid = document.getElementById("metricsGrid");
const zonesTableBody = document.getElementById("zonesTableBody");

const chartRefs = {
  supplyVsBilled: null,
  lossPerZone: null,
  distributionPie: null,
  trendsLine: null,
};

const chartColors = {
  supplied: "rgba(18, 130, 162, 0.82)",
  billed: "rgba(243, 167, 18, 0.82)",
  loss: "rgba(192, 57, 43, 0.8)",
  lineA: "#0b7e9b",
  lineB: "#e09313",
  lineC: "#c0392b",
};

function formatNumber(value) {
  return Number(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function buildMetricCard(label, value) {
  return `
    <article class="metric">
      <p class="metric__label">${label}</p>
      <p class="metric__value">${value}</p>
    </article>
  `;
}

function renderMetrics(metrics, metricLabels = {}) {
  const suppliedLabel = metricLabels.total_supplied || "Total Supplied";
  const billedLabel = metricLabels.total_billed || "Total Billed";
  const lossLabel = metricLabels.total_loss || "Total Loss";
  const percentageLabel = metricLabels.loss_percentage || "Loss %";

  metricsGrid.innerHTML = [
    buildMetricCard("Zones", formatNumber(metrics.zone_count)),
    buildMetricCard(suppliedLabel, formatNumber(metrics.total_supplied)),
    buildMetricCard(billedLabel, formatNumber(metrics.total_billed)),
    buildMetricCard(lossLabel, formatNumber(metrics.total_loss)),
    buildMetricCard(percentageLabel, `${formatNumber(metrics.loss_percentage)}%`),
    buildMetricCard("Threshold", formatNumber(metrics.threshold)),
    buildMetricCard("Alerts", formatNumber(metrics.alerts_count)),
  ].join("");
}

function renderAlerts(alerts) {
  if (!alerts.length) {
    alertsList.innerHTML = '<li class="alert-item ok">No leakage alerts detected for the current threshold.</li>';
    return;
  }

  alertsList.innerHTML = alerts
    .map((alert) => `<li class="alert-item">${alert.message}</li>`)
    .join("");
}

function renderZoneTable(zoneTable) {
  if (!zoneTable || zoneTable.length === 0) {
    zonesTableBody.innerHTML =
      '<tr><td colspan="5" class="empty-row">No zone records available for the selected dataset.</td></tr>';
    return;
  }

  zonesTableBody.innerHTML = zoneTable
    .map(
      (item) => `
      <tr>
        <td>${item.zone}</td>
        <td>${formatNumber(item.water_supplied)}</td>
        <td>${formatNumber(item.water_billed)}</td>
        <td>${formatNumber(item.water_loss)}</td>
        <td>
          <span class="status-pill ${item.leak_flag ? "leak" : "safe"}">
            ${item.leak_flag ? "Leak Suspected" : "Normal"}
          </span>
        </td>
      </tr>
      `
    )
    .join("");
}

function destroyCharts() {
  Object.keys(chartRefs).forEach((key) => {
    if (chartRefs[key]) {
      chartRefs[key].destroy();
      chartRefs[key] = null;
    }
  });
}

function renderCharts(payload) {
  destroyCharts();

  chartRefs.supplyVsBilled = new Chart(document.getElementById("supplyVsBilledChart"), {
    type: "bar",
    data: {
      labels: payload.zones.labels,
      datasets: [
        {
          label: "Water Supplied",
          data: payload.zones.supplied,
          backgroundColor: chartColors.supplied,
          borderRadius: 7,
        },
        {
          label: "Water Billed",
          data: payload.zones.billed,
          backgroundColor: chartColors.billed,
          borderRadius: 7,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "top" } },
      scales: {
        y: { beginAtZero: true },
      },
    },
  });

  chartRefs.lossPerZone = new Chart(document.getElementById("lossPerZoneChart"), {
    type: "bar",
    data: {
      labels: payload.zones.labels,
      datasets: [
        {
          label: "Water Loss",
          data: payload.zones.loss,
          backgroundColor: payload.zones.leak_flags.map((flag) =>
            flag ? "rgba(192, 57, 43, 0.8)" : "rgba(139, 177, 116, 0.8)"
          ),
          borderRadius: 7,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true },
      },
    },
  });

  chartRefs.distributionPie = new Chart(document.getElementById("distributionPieChart"), {
    type: "pie",
    data: {
      labels: payload.distribution.labels,
      datasets: [
        {
          data: payload.distribution.supplied_share,
          backgroundColor: [
            "#0f7390",
            "#f3a712",
            "#8bb174",
            "#3f88c5",
            "#db504a",
            "#5f0f40",
            "#0a9396",
          ],
        },
      ],
    },
    options: {
      responsive: true,
    },
  });

  const trendAvailable = payload.trends.labels.length > 0;
  const trendData = trendAvailable
    ? payload.trends
    : { labels: ["No Date Column"], supplied: [0], billed: [0], loss: [0] };

  chartRefs.trendsLine = new Chart(document.getElementById("trendsLineChart"), {
    type: "line",
    data: {
      labels: trendData.labels,
      datasets: [
        {
          label: "Supplied",
          data: trendData.supplied,
          borderColor: chartColors.lineA,
          backgroundColor: "rgba(11, 126, 155, 0.2)",
          tension: 0.3,
        },
        {
          label: "Billed",
          data: trendData.billed,
          borderColor: chartColors.lineB,
          backgroundColor: "rgba(224, 147, 19, 0.2)",
          tension: 0.3,
        },
        {
          label: "Loss",
          data: trendData.loss,
          borderColor: chartColors.lineC,
          backgroundColor: "rgba(192, 57, 43, 0.2)",
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      scales: {
        y: { beginAtZero: true },
      },
      plugins: {
        subtitle: {
          display: !trendAvailable,
          text: "Upload data with a date column to see time-based trends.",
        },
      },
    },
  });
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(uploadForm);
  statusMessage.textContent = "Processing dataset...";

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to analyze data.");
    }

    renderMetrics(payload.metrics, payload.metric_labels);
    renderAlerts(payload.alerts);
    renderZoneTable(payload.zones.table);
    renderCharts(payload);
    modeInfo.textContent = `Mode: ${payload.mode_label || "Water Loss Analysis"}`;
    statusMessage.textContent = "Analysis complete. Dashboard updated.";
  } catch (error) {
    modeInfo.textContent = "";
    statusMessage.textContent = error.message;
  }
});

sampleBtn.addEventListener("click", async () => {
  const threshold = document.getElementById("threshold").value || "50";
  statusMessage.textContent = "Analyzing sample dataset...";

  try {
    const response = await fetch(`/api/analyze-sample?threshold=${encodeURIComponent(threshold)}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to analyze sample data.");
    }

    renderMetrics(payload.metrics, payload.metric_labels);
    renderAlerts(payload.alerts);
    renderZoneTable(payload.zones.table);
    renderCharts(payload);
    modeInfo.textContent = `Mode: ${payload.mode_label || "Water Loss Analysis"}`;
    statusMessage.textContent = `Sample analysis complete (${payload.sample_file}).`;
  } catch (error) {
    modeInfo.textContent = "";
    statusMessage.textContent = error.message;
  }
});
