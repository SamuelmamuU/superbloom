document.addEventListener('DOMContentLoaded', () => {

    // --- CONFIGURACIÓN ---
    const MAPBOX_TOKEN = 'sk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A'; // <-- REEMPLAZA ESTO
    const MAPBOX_STYLE_URL = `https://api.mapbox.com/styles/v1/mapbox/dark-v11/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`;
    const MAPBOX_ATTRIBUTION = '© Mapbox';

    // --- ELEMENTOS DEL DOM ---
    const navButtons = document.querySelectorAll('.nav-button');
    const views = document.querySelectorAll('.view');
    const form = document.getElementById('analysis-form');
    const submitButton = document.getElementById('submit-button');
    const loadingIndicator = document.getElementById('loading');
    const keyMetricsContainer = document.getElementById('key-metrics');
    const detailedDashboardContainer = document.getElementById('detailed-dashboard');

    // --- ESTADO DE LA APLICACIÓN ---
    let map;
    let layerControl;
    let geeLayers = {};

    // ===========================================
    // 1. INICIALIZACIÓN Y MANEJO DE VISTAS
    // ===========================================
    function initMap() {
        map = L.map('map', { zoomControl: false }).setView([32.62, -115.46], 10);
        L.tileLayer(MAPBOX_STYLE_URL, { attribution: MAPBOX_ATTRIBUTION, tileSize: 512, zoomOffset: -1 }).addTo(map);
        L.control.zoom({ position: 'bottomright' }).addTo(map);
        layerControl = L.control.layers(null, null, { collapsed: false, position: 'topright' }).addTo(map);
    }
    
    function handleViewChange(viewId) {
        // Actualizar botones de navegación
        navButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === viewId);
        });
        // Actualizar vista activa
        views.forEach(view => {
            view.classList.toggle('active', view.id === `${viewId}-view`);
        });
    }

    navButtons.forEach(button => {
        button.addEventListener('click', () => handleViewChange(button.dataset.view));
    });

    initMap();

    // ===========================================
    // 2. LLAMADA A LA API Y MANEJO DE DATOS
    // ===========================================
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        submitButton.disabled = true;
        loadingIndicator.classList.remove('hidden');
        keyMetricsContainer.innerHTML = '<h3>Cargando métricas...</h3>';
        detailedDashboardContainer.innerHTML = '<h3>Cargando datos detallados...</h3>';

        const payload = {
            coords: [
                parseFloat(document.getElementById('xmin').value),
                parseFloat(document.getElementById('ymin').value),
                parseFloat(document.getElementById('xmax').value),
                parseFloat(document.getElementById('ymax').value)
            ],
            historic_start: document.getElementById('historic-start').value,
            historic_end: document.getElementById('historic-end').value,
            current_start: document.getElementById('current-start').value,
            current_end: document.getElementById('current-end').value
        };

        try {
            const response = await fetch('/analizar-completo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error((await response.json()).error || 'Error en el servidor.');
            
            const results = await response.json();
            updateMap(results.map_data);
            updateDashboard(results.dashboard_data);

        } catch (error) {
            keyMetricsContainer.innerHTML = `<p style="color: #F87171;">${error.message}</p>`;
            detailedDashboardContainer.innerHTML = '';
        } finally {
            submitButton.disabled = false;
            loadingIndicator.classList.add('hidden');
        }
    });

    // ===========================================
    // 3. FUNCIONES DE ACTUALIZACIÓN DE LA UI
    // ===========================================
    function updateMap(mapData) {
        Object.values(geeLayers).forEach(layer => layerControl.removeLayer(layer));
        Object.values(geeLayers).forEach(layer => map.removeLayer(layer));

        geeLayers.actual = L.tileLayer(mapData.tile_urls.actual, { opacity: 0.8 });
        geeLayers.historico = L.tileLayer(mapData.tile_urls.historico, { opacity: 0.8 });
        geeLayers.diferencia = L.tileLayer(mapData.tile_urls.diferencia, { opacity: 0.8 });
        
        layerControl.addOverlay(geeLayers.actual, 'NDVI Actual');
        layerControl.addOverlay(geeLayers.historico, 'NDVI Histórico');
        layerControl.addOverlay(geeLayers.diferencia, 'Contraste NDVI');
        
        geeLayers.diferencia.addTo(map);
        map.flyTo(mapData.centro, 10);
    }

    function updateDashboard(data) {
        const formatValue = (val, decimals = 4) => (val !== null && val !== undefined) ? parseFloat(val).toFixed(decimals) : 'N/A';
        const change = data.comparativo.cambio_ndvi.valor;
        const changeClass = change > 0 ? 'up' : 'down';
        const changeSign = change > 0 ? '+' : '';

        // --- Actualizar Métricas Clave ---
        keyMetricsContainer.innerHTML = `
            <div class="metric-card">
                <div class="metric-card-header"><span>NDVI Actual</span></div>
                <div class="metric-card-body"><div class="value">${formatValue(data.actual.ndvi.valor)}</div></div>
                <div class="metric-card-footer ${changeClass}">
                    <span>${changeSign}${formatValue(change)}</span>
                    <span>vs. histórico</span>
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-card-header"><span>Temperatura (LST)</span></div>
                <div class="metric-card-body"><div class="value">${formatValue(data.actual.lst_celsius.valor, 2)} °C</div></div>
                <div class="metric-card-footer"><span>${data.actual.lst_celsius.interpretacion}</span></div>
            </div>
            <div class="metric-card">
                <div class="metric-card-header"><span>Índice Floral (NDSI)</span></div>
                <div class="metric-card-body"><div class="value">${formatValue(data.actual.ndsi_floral.valor)}</div></div>
                <div class="metric-card-footer"><span>${data.actual.ndsi_floral.interpretacion}</span></div>
            </div>
            <div class="metric-card">
                <div class="metric-card-header"><span>Índice Mejorado (EVI)</span></div>
                <div class="metric-card-body"><div class="value">${formatValue(data.actual.evi.valor)}</div></div>
                <div class="metric-card-footer"><span>${data.actual.evi.interpretacion}</span></div>
            </div>
        `;

        // --- Actualizar Dashboard Detallado ---
        detailedDashboardContainer.innerHTML = `
            <h2>Dashboard Detallado</h2>
            <div class="results-grid">
                <div class="result-card">
                    <h3>NDVI Actual</h3>
                    <p class="valor">${formatValue(data.actual.ndvi.valor)}</p>
                    <p class="interpretacion">${data.actual.ndvi.interpretacion}</p>
                </div>
                <div class="result-card">
                    <h3>NDVI Histórico</h3>
                    <p class="valor">${formatValue(data.comparativo.ndvi_historico.valor)}</p>
                    <p class="interpretacion">Valor de referencia para la comparación.</p>
                </div>
                <div class="result-card">
                    <h3>Cambio Neto de NDVI</h3>
                    <p class="valor ${changeClass}">${changeSign}${formatValue(change)}</p>
                    <p class="interpretacion">${data.comparativo.cambio_ndvi.interpretacion}</p>
                </div>
                <div class="result-card">
                    <h3>Temperatura (LST)</h3>
                    <p class="valor">${formatValue(data.actual.lst_celsius.valor, 2)} °C</p>
                    <p class="interpretacion">${data.actual.lst_celsius.interpretacion}</p>
                </div>
                <div class="result-card">
                    <h3>Índice Floral (NDSI)</h3>
                    <p class="valor">${formatValue(data.actual.ndsi_floral.valor)}</p>
                    <p class="interpretacion">${data.actual.ndsi_floral.interpretacion}</p>
                </div>
                <div class="result-card">
                    <h3>Índice Mejorado (EVI)</h3>
                    <p class="valor">${formatValue(data.actual.evi.valor)}</p>
                    <p class="interpretacion">${data.actual.evi.interpretacion}</p>
                </div>
            </div>
        `;
    }
});