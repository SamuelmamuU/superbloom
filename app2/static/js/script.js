document.addEventListener('DOMContentLoaded', () => {

     // --- CONFIGURACIÓN ---
    const MAPBOX_TOKEN = 'sk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A'; // <-- REEMPLAZA ESTO
    const MAPBOX_STYLE_URL = `https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`;
    const MAPBOX_ATTRIBUTION = '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a>';

    // --- ELEMENTOS DEL DOM ---
    const navButtons = document.querySelectorAll('.nav-button');
    const views = document.querySelectorAll('.view');
    const form = document.getElementById('analysis-form');
    const submitButton = document.getElementById('submit-button');
    const loadingIndicator = document.getElementById('loading');
    const keyMetricsContainer = document.getElementById('key-metrics');
    const detailedDashboardContainer = document.getElementById('detailed-dashboard');
    const layerControlsContainer = document.getElementById('layer-controls');

    // --- ESTADO DE LA APLICACIÓN ---
    let map;
    let geeLayers = {};

    // ===========================================
    // 1. INICIALIZACIÓN Y MANEJO DE VISTAS
    // ===========================================
    function initMap() {
        map = L.map('map', { zoomControl: false }).setView([32.62, -115.46], 10);
        L.tileLayer(MAPBOX_STYLE_URL, { attribution: MAPBOX_ATTRIBUTION, tileSize: 512, zoomOffset: -1 }).addTo(map);
        L.control.zoom({ position: 'bottomright' }).addTo(map);
    }
    
    function handleViewChange(viewId) {
        navButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.view === viewId));
        views.forEach(view => view.classList.toggle('active', view.id === `${viewId}-view`));
    }

    navButtons.forEach(button => {
        button.addEventListener('click', () => handleViewChange(button.dataset.view));
    });

    initMap();

    // ===========================================
    // 2. LLAMADA A LA API Y MANEJO DE DATOS
    // ===========================================
    form.addEventListener('submit', async (event) => {
        // Previene que la página se recargue al enviar el formulario
        event.preventDefault();
        
        // --- 1. Prepara la interfaz para la carga ---
        submitButton.disabled = true;
        loadingIndicator.classList.remove('hidden'); // Muestra el spinner
        keyMetricsContainer.innerHTML = '<p class="placeholder">Cargando métricas...</p>';
        detailedDashboardContainer.innerHTML = '';
        layerControlsContainer.innerHTML = '<p class="placeholder">Generando capas...</p>';

        // --- 2. Reúne todos los datos del formulario ---
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

        // --- 3. Llama al servidor y espera la respuesta ---
        try {
            const response = await fetch('/analizar-completo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            // Si la respuesta del servidor no es exitosa, genera un error
            if (!response.ok) {
                throw new Error((await response.json()).error || 'Error en el servidor.');
            }
            
            // Si todo fue exitoso, procesa los resultados
            const results = await response.json();
            updateMap(results.map_data);
            updateDashboard(results.dashboard_data);

        } catch (error) {
            // Si ocurre cualquier error, muéstralo en la interfaz
            keyMetricsContainer.innerHTML = `<p class="placeholder" style="color: #F87171;">${error.message}</p>`;
            layerControlsContainer.innerHTML = '<p class="placeholder">Error al generar capas.</p>';
            console.error("Error en el análisis:", error);
        } finally {
            // --- 4. Limpia la interfaz sin importar el resultado ---
            submitButton.disabled = false;
            loadingIndicator.classList.add('hidden'); // Oculta el spinner
        }
    });

    // ===========================================
    // 3. FUNCIONES DE ACTUALIZACIÓN DE LA UI
    // ===========================================
    function updateMap(mapData) {
        Object.values(geeLayers).forEach(layer => map.removeLayer(layer));

        geeLayers.actual = L.tileLayer(mapData.tile_urls.actual, { opacity: 0.8 });
        geeLayers.historico = L.tileLayer(mapData.tile_urls.historico, { opacity: 0.8 });
        geeLayers.diferencia = L.tileLayer(mapData.tile_urls.diferencia, { opacity: 0.8 });
        
        generateLayerControls();
        map.flyTo(mapData.centro, 10);
    }
    
    function generateLayerControls() {
        const layersConfig = [
            { id: 'diferencia', name: 'Contraste NDVI', checked: true },
            { id: 'actual', name: 'NDVI Actual', checked: false },
            { id: 'historico', name: 'NDVI Histórico', checked: false }
        ];

        layerControlsContainer.innerHTML = ''; // Limpiar controles
        
        layersConfig.forEach(config => {
            const layerItem = document.createElement('div');
            layerItem.className = 'layer-item';
            layerItem.dataset.layer = config.id;

            // Usamos 'radio' en lugar de 'checkbox'
            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.id = `radio-${config.id}`;
            radio.name = 'layer-selection'; // El mismo 'name' los agrupa
            radio.value = config.id;
            radio.checked = config.checked;
            
            const label = document.createElement('label');
            label.htmlFor = `radio-${config.id}`;
            label.textContent = config.name;

            layerItem.appendChild(radio);
            layerItem.appendChild(label);
            layerControlsContainer.appendChild(layerItem);

            // Añadir capa al mapa si está marcada por defecto
            if (config.checked) {
                map.addLayer(geeLayers[config.id]);
            }

            // El evento ahora maneja la lógica de radio-button
            radio.addEventListener('change', (e) => {
                // Primero, quitamos todas las capas del mapa
                Object.values(geeLayers).forEach(layer => map.removeLayer(layer));
                // Luego, añadimos solo la capa seleccionada
                if (e.target.checked) {
                    map.addLayer(geeLayers[e.target.value]);
                }
            });
        });
    }

    function updateDashboard(data) {
        const formatValue = (val, decimals = 4) => (val !== null && val !== undefined) ? parseFloat(val).toFixed(decimals) : 'N/A';
        const change = data.comparativo.cambio_ndvi.valor;
        const changeClass = change > 0.01 ? 'up' : change < -0.01 ? 'down' : '';
        const changeSign = change > 0 ? '+' : '';

        keyMetricsContainer.innerHTML = `
            <div class="metric-card">
                <div class="metric-card-header"><span>NDVI Actual</span></div>
                <div class="metric-card-body"><div class="value">${formatValue(data.actual.ndvi.valor)}</div></div>
                <div class="metric-card-footer ${changeClass}">
                    <span>${change ? `${changeSign}${formatValue(change)}` : '-'}</span>
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
                    <p class="valor ${changeClass}">${change ? `${changeSign}${formatValue(change)}` : 'N/A'}</p>
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