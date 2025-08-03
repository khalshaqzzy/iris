// server-kebakaran/static/chart.js

document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM Fully Loaded. chart.js execution started.");

    const roomsGrid = document.getElementById('roomsGrid');
    const loadingPlaceholder = document.getElementById('loadingPlaceholder');
    const overallStatusDiv = document.getElementById('overall-status');
    const systemStatusText = document.getElementById('system-status-text');
    if(document.getElementById('currentYear')) {
        document.getElementById('currentYear').textContent = new Date().getFullYear();
    }

    let roomCharts = {}; 
    let fireAlertEverTriggered = false; // <-- VARIABEL GLOBAL UNTUK MELACAK STATUS KEBAKARAN

    const chartDefaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
            duration: 400,
            easing: 'easeInOutQuad'
        },
        scales: {
            x: {
                ticks: { 
                    display: true, 
                    maxRotation: 0, 
                    minRotation: 0, 
                    autoSkipPadding: 15, 
                    font: { size: 10, family: 'Inter' },
                    color: 'var(--color-muted)'
                },
                grid: { display: false }
            },
            y: {
                beginAtZero: false,
                grid: { 
                    color: 'var(--color-border)', 
                    drawBorder: false,
                    borderDash: [2, 3], 
                },
                ticks: { 
                    padding: 8, 
                    font: { size: 10, family: 'Inter' },
                    color: 'var(--color-muted)',
                    maxTicksLimit: 5 
                }
            }
        },
        plugins: {
            legend: { 
                display: true, 
                position: 'bottom', 
                align: 'start',
                labels: { 
                    boxWidth: 10, 
                    padding: 10,
                    font: { size: 11, family: 'Inter' },
                    color: 'var(--color-secondary)'
                } 
            },
            tooltip: {
                enabled: true,
                mode: 'index',
                intersect: false,
                backgroundColor: 'rgba(0,0,0,0.8)',
                titleFont: { family: 'Inter', weight: '600', size: 13 },
                bodyFont: { family: 'Inter', size: 12 },
                padding: 10,
                cornerRadius: 6,
                callbacks: {
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) { label += ': '; }
                        if (context.parsed.y !== null) {
                            label += context.parsed.y.toFixed(1);
                            if (context.dataset.label.toLowerCase().includes('suhu')) label += '°C';
                        }
                        return label;
                    }
                }
            }
        },
        elements: {
            line: { tension: 0.4, borderWidth: 2.5 }, 
            point: { radius: 0, hoverRadius: 5, hitRadius: 10 } 
        }
    };


    function createRoomCard(roomId) {
        const card = document.createElement('div');
        card.className = 'room-card';
        card.id = `card-${roomId}`;

        card.innerHTML = `
            <div class="card-header">
                <h2><i class="fas fa-broadcast-tower"></i> ${roomId.replace(/_/g, ' ')}</h2>
                <span class="status-badge" id="status-${roomId}">MEMUAT...</span>
            </div>
            <div class="card-content-wrapper">
                <div class="sensor-and-chart-column">
                    <div class="sensor-readings">
                        <div class="sensor-reading-item">
                            <i class="fas fa-temperature-half temp-icon"></i>
                            Suhu
                            <span class="value" id="temp-${roomId}">N/A</span>
                        </div>
                        <div class="sensor-reading-item">
                            <i class="fas fa-smog smoke-icon"></i>
                            Asap
                            <span class="value" id="smoke-${roomId}">N/A</span>
                        </div>
                    </div>
                    <div class="people-detection-reading" id="people-reading-${roomId}" style="display: none;">
                        <i class="fas fa-users people-icon"></i>
                        Orang Terdeteksi
                        <span class="value" id="people-${roomId}">N/A</span>
                    </div>
                    <div class="chart-group">
                        <div class="chart-container">
                            <canvas id="chart-${roomId}-temp"></canvas>
                        </div>
                    </div>
                    <div class="chart-group">
                        <div class="chart-container">
                            <canvas id="chart-${roomId}-smoke"></canvas>
                        </div>
                    </div>
                </div>
                <div class="detection-image-column" id="image-column-${roomId}" style="display: none;">
                    <div class="detection-image-container" id="image-container-${roomId}">
                        <img src="" alt="Deteksi Ruangan ${roomId}" id="image-${roomId}">
                        <div class="image-overlay">Gambar Deteksi</div>
                    </div>
                </div>
            </div>
            <div class="card-footer">
                Terakhir Update: <span id="update-${roomId}">N/A</span>
            </div>
        `;
        roomsGrid.appendChild(card);

        const tempCtx = document.getElementById(`chart-${roomId}-temp`)?.getContext('2d');
        const smokeCtx = document.getElementById(`chart-${roomId}-smoke`)?.getContext('2d');

        if (!tempCtx || !smokeCtx) {
            console.error(`Canvas context not found for ${roomId}.`);
            return;
        }

        let tempChartOptions = JSON.parse(JSON.stringify(chartDefaultOptions));
        let smokeChartOptions = JSON.parse(JSON.stringify(chartDefaultOptions));
        smokeChartOptions.scales.y.beginAtZero = true;

        try {
            roomCharts[roomId] = {
                tempChart: new Chart(tempCtx, {
                    type: 'line',
                    data: { labels: [], datasets: [{ label: 'Suhu (°C)', data: [], borderColor: 'var(--temp-chart-color)', backgroundColor: 'rgba(255, 120, 89, 0.1)', fill: 'origin' }] },
                    options: tempChartOptions
                }),
                smokeChart: new Chart(smokeCtx, {
                    type: 'line',
                    data: { labels: [], datasets: [{ label: 'Nilai Asap', data: [], borderColor: 'var(--smoke-chart-color)', backgroundColor: 'rgba(0, 119, 182, 0.1)', fill: 'origin' }] },
                    options: smokeChartOptions
                })
            };
        } catch (e) {
            console.error(`Failed to initialize Chart for ${roomId}`, e);
        }
    }

    function updateRoomCard(roomId, data) {
        if (!document.getElementById(`card-${roomId}`)) {
            createRoomCard(roomId);
        }

        const statusBadge = document.getElementById(`status-${roomId}`);
        if (statusBadge) {
            statusBadge.textContent = data.status.replace(/_/g, ' ');
            statusBadge.className = `status-badge status-${data.status}`;
        }

        document.getElementById(`temp-${roomId}`).textContent = data.temperature_current !== null ? `${data.temperature_current.toFixed(1)} °C` : 'N/A';
        document.getElementById(`smoke-${roomId}`).textContent = data.smoke_current !== null ? data.smoke_current : 'N/A';
        
        const updateTimeEl = document.getElementById(`update-${roomId}`);
        if (updateTimeEl) {
            let lastUpdateText = 'N/A';
            if (data.last_update_iso) {
                try {
                    lastUpdateText = luxon.DateTime.fromISO(data.last_update_iso).toRelative({ base: luxon.DateTime.now(), style: 'short' }) || 
                                     luxon.DateTime.fromISO(data.last_update_iso).toLocaleString(luxon.DateTime.TIME_SIMPLE);
                } catch (e) { lastUpdateText = data.last_update_iso; }
            }
            updateTimeEl.textContent = lastUpdateText;
        }

        const peopleReadingContainer = document.getElementById(`people-reading-${roomId}`);
        const peopleCountValue = document.getElementById(`people-${roomId}`);

        // Tampilkan jika alarm global pernah berbunyi DAN ada data orang yang valid
        if (fireAlertEverTriggered && data.people_count >= 0) {
            peopleCountValue.textContent = data.people_count;
            peopleReadingContainer.style.display = 'flex';
        } else {
            peopleReadingContainer.style.display = 'none';
        }

        // Logika untuk menampilkan gambar deteksi
        const imageColumn = document.getElementById(`image-column-${roomId}`);
        const imageEl = document.getElementById(`image-${roomId}`);
        if (fireAlertEverTriggered && data.detection_image_url) {
            imageColumn.style.display = 'flex';
            // Hanya perbarui src jika berbeda untuk menghindari kedipan yang tidak perlu
            if (imageEl.src !== data.detection_image_url) {
                imageEl.src = data.detection_image_url;
            }
        } else {
            imageColumn.style.display = 'none';
        }

        if (roomCharts[roomId] && roomCharts[roomId].tempChart) {
            roomCharts[roomId].tempChart.data.labels = data.labels || [];
            roomCharts[roomId].tempChart.data.datasets[0].data = data.temperatures || [];
            roomCharts[roomId].tempChart.update('none');
        }

        if (roomCharts[roomId] && roomCharts[roomId].smokeChart) {
            roomCharts[roomId].smokeChart.data.labels = data.labels || [];
            roomCharts[roomId].smokeChart.data.datasets[0].data = data.smokeValues || [];
            roomCharts[roomId].smokeChart.update('none');
        }
    }

    function updateOverallStatus(roomsData) {
        let systemInAlertFire = false;
        let systemHasMissingOrStale = false;
        let roomCount = Object.keys(roomsData).length;
        let overallStatusClass = 'overall-status-NORMAL'; 

        if (roomCount === 0) {
            if(systemStatusText) systemStatusText.textContent = "Belum ada data";
            overallStatusClass = 'overall-status-UNKNOWN'; 
            if(overallStatusDiv) overallStatusDiv.className = `overall-status-chip ${overallStatusClass}`;
            return;
        }

        for (const roomId in roomsData) {
            if (roomsData[roomId].status === 'ALERT_FIRE') {
                systemInAlertFire = true;
                break; 
            } else if (roomsData[roomId].status === 'ALERT_MISSING' || roomsData[roomId].status === 'STALE') {
                systemHasMissingOrStale = true;
            }
        }

        if (systemInAlertFire) {
            if(systemStatusText) systemStatusText.textContent = "KEBAKARAN TERDETEKSI!";
            overallStatusClass = 'overall-status-ALERT_FIRE';
        } else if (systemHasMissingOrStale) {
            if(systemStatusText) systemStatusText.textContent = "Peringatan Sistem"; 
            overallStatusClass = 'overall-status-ALERT_MISSING'; 
        } else {
            if(systemStatusText) systemStatusText.textContent = "Semua Normal";
            overallStatusClass = 'overall-status-NORMAL';
        }
        if(overallStatusDiv) overallStatusDiv.className = `overall-status-chip ${overallStatusClass}`;
    }


    async function fetchDataAndUpdate() {
        try {
            const response = await fetch('/get_live_data');
            if (!response.ok) {
                throw new Error(`Gagal mengambil data: ${response.status} ${response.statusText}`);
            }
            const data = await response.json();

            // Perbarui status alarm global dari data yang diterima
            fireAlertEverTriggered = data.fire_alert_triggered;
            
            // Ambil data ruangan untuk diproses
            const dataByRoom = data.rooms;

            if (loadingPlaceholder) {
                if (Object.keys(dataByRoom).length > 0) {
                    if (document.body.contains(loadingPlaceholder)) loadingPlaceholder.style.display = 'none';
                } else {
                    if (document.body.contains(loadingPlaceholder)) {
                        loadingPlaceholder.innerHTML = `<div class="spinner"></div><p>Menunggu data sensor pertama...</p>`;
                        loadingPlaceholder.style.display = 'flex';
                    }
                }
            }
            
            const currentDisplayedRoomIds = new Set(Object.keys(roomCharts));
            const incomingRoomIds = new Set(Object.keys(dataByRoom));

            incomingRoomIds.forEach(roomId => {
                if (!currentDisplayedRoomIds.has(roomId)) {
                    createRoomCard(roomId);
                }
                updateRoomCard(roomId, dataByRoom[roomId]);
            });
            
            updateOverallStatus(dataByRoom);

        } catch (error) {
            console.error("Error dalam fetchDataAndUpdate:", error);
            if (loadingPlaceholder && document.body.contains(loadingPlaceholder)) {
                loadingPlaceholder.innerHTML = `<i class="fas fa-exclamation-triangle"></i><p>Gagal memuat data. Periksa koneksi atau server.</p>`;
                loadingPlaceholder.style.display = 'flex';
            }
            if (systemStatusText) systemStatusText.textContent = "Error Sistem";
            if (overallStatusDiv) overallStatusDiv.className = "overall-status-chip overall-status-ALERT_MISSING";
        }
    }

    if (roomsGrid && loadingPlaceholder && overallStatusDiv && systemStatusText) {
        fetchDataAndUpdate();
        setInterval(fetchDataAndUpdate, 2000); 
    } else {
        console.error("Elemen penting halaman tidak ditemukan. Skrip tidak akan berjalan dengan benar.");
    }
});