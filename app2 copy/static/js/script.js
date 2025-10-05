document.addEventListener('DOMContentLoaded', () => {
    // --- CONFIGURACIÓN ---
    const MAPBOX_TOKEN = 'sk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A';
    const MAPBOX_STYLE_URL = `https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`;
    const MAPBOX_ATTRIBUTION = '© Mapbox';

    // --- ELEMENTOS DEL DOM ---
    const navButtons = document.querySelectorAll('.nav-button');
    const views = document.querySelectorAll('.view');
    const form = document.getElementById('analysis-form');
    const submitButton = document.getElementById('submit-button');
    const keyMetricsContainer = document.getElementById('key-metrics');
    const detailedDashboardContainer = document.getElementById('detailed-dashboard');
    const layerGroupsContainer = document.getElementById('layer-groups-container');

    // --- ESTADO DE LA APLICACIÓN ---
    let map;
    let geeLayers = {}; // Almacenará todas las capas GEE por variable y período
    window.currentBounds = null; // Bounds del mapa

    // ===========================================
    // 1. INICIALIZACIÓN Y MANEJO DE VISTAS
    // ===========================================
    function initMap(bounds) {
        // Calcular centro a partir de bounds
        const centerLat = (bounds[0][0] + bounds[1][0]) / 2;
        const centerLon = (bounds[0][1] + bounds[1][1]) / 2;

        map = L.map('map', { 
            zoomControl: false,
            maxBounds: bounds,          // Limita el arrastre al área de la capa
            maxBoundsViscosity: 1.0     // Evita que se salga del área
        }).setView([centerLat, centerLon], 10);

        // Capa base
        L.tileLayer(MAPBOX_STYLE_URL, { 
            attribution: MAPBOX_ATTRIBUTION, 
            tileSize: 512, 
            zoomOffset: -1 
        }).addTo(map);

        // Control de zoom
        L.control.zoom({ position: 'bottomright' }).addTo(map);
    }
    
    navButtons.forEach(button => {
        button.addEventListener('click', () => {
            navButtons.forEach(btn => btn.classList.remove('active'));
            views.forEach(view => view.classList.remove('active'));
            button.classList.add('active');
            document.getElementById(`${button.dataset.view}-view`).classList.add('active');
        });
    });

    // Inicializar mapa con bounds temporales (se actualizarán después)
    initMap([[0, 0], [0, 0]]);

    // ===========================================
    // 2. LLAMADA A LA API Y MANEJO DE DATOS
    // ===========================================
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        submitButton.disabled = true;
        keyMetricsContainer.innerHTML = '<p class="placeholder">Cargando métricas...</p>';
        detailedDashboardContainer.innerHTML = '';
        layerGroupsContainer.innerHTML = '<p class="placeholder">Generando capas...</p>';

        const payload = {
            coords: [
                parseFloat(document.getElementById('xmin').value), parseFloat(document.getElementById('ymin').value),
                parseFloat(document.getElementById('xmax').value), parseFloat(document.getElementById('ymax').value)
            ],
            historic_start: document.getElementById('historic-start').value, historic_end: document.getElementById('historic-end').value,
            current_start: document.getElementById('current-start').value, current_end: document.getElementById('current-end').value
        };

        // Guardar bounds globalmente para maxBounds
        window.currentBounds = [
            [payload.coords[1], payload.coords[0]], // [ymin, xmin]
            [payload.coords[3], payload.coords[2]]  // [ymax, xmax]
        ];

        // Re-inicializar mapa con bounds reales
        initMap(window.currentBounds);

        try {
            const response = await fetch('/analizar-avanzado', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
            });
            if (!response.ok) throw new Error((await response.json()).error || 'Error en servidor.');
            
            const results = await response.json();
            updateMap(results.map_data);
            updateDashboard(results.dashboard_data);
        } catch (error) {
            keyMetricsContainer.innerHTML = `<p class="placeholder" style="color: #F87171;">${error.message}</p>`;
            layerGroupsContainer.innerHTML = '<p class="placeholder">Error al generar capas.</p>';
        } finally {
            submitButton.disabled = false;
        }
    });

    // ===========================================
    // 3. FUNCIONES DE ACTUALIZACIÓN DE LA UI
    // ===========================================
    function updateMap(mapData) {
        // Eliminar capas anteriores
        Object.values(geeLayers).flat().forEach(layer => map.removeLayer(layer));
        geeLayers = {}; // Reset

        // Crear nuevas capas con opacidad 0.5
        for (const variable in mapData.tile_urls) {
            geeLayers[variable] = {};
            for (const periodo in mapData.tile_urls[variable]) {
                geeLayers[variable][periodo] = L.tileLayer(mapData.tile_urls[variable][periodo], { opacity: 0.5 });
            }
        }

        // Generar controles de capas
        generateLayerControls();

        // Ajustar el centro del mapa
        map.flyTo(mapData.centro, 10);

        // Aplicar bounds máximos
        if (window.currentBounds) {
            map.setMaxBounds(window.currentBounds);
        }
    }
    
    function generateLayerControls() {
        const layersConfig = [
            { id: 'ndvi-diferencia', name: 'Contraste NDVI', variable: 'ndvi', period: 'diferencia', checked: true },
            { id: 'ndvi-actual', name: 'NDVI Actual', variable: 'ndvi', period: 'actual', checked: false },
            { id: 'ndvi-historico', name: 'NDVI Histórico', variable: 'ndvi', period: 'historico', checked: false },
            { id: 'temperatura-diferencia', name: 'Contraste Temp.', variable: 'temperatura', period: 'diferencia', checked: false },
            { id: 'temperatura-actual', name: 'Temp. Actual', variable: 'temperatura', period: 'actual', checked: false },
            { id: 'temperatura-historico', name: 'Temp. Histórica', variable: 'temperatura', period: 'historico', checked: false },
            { id: 'precipitacion-diferencia', name: 'Contraste Precip.', variable: 'precipitacion', period: 'diferencia', checked: false },
            { id: 'precipitacion-actual', name: 'Precip. Actual', variable: 'precipitacion', period: 'actual', checked: false },
            { id: 'precipitacion-historico', name: 'Precip. Histórica', variable: 'precipitacion', period: 'historico', checked: false },
        ];

        layerGroupsContainer.innerHTML = ''; // Limpiar
        const grid = document.createElement('div');
        grid.className = 'layer-grid';

        layersConfig.forEach(config => {
            const label = document.createElement('label');
            label.className = 'layer-grid-item';
            label.htmlFor = `radio-${config.id}`;
            label.dataset.variable = config.variable;

            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.id = `radio-${config.id}`;
            radio.name = 'layer-selection';
            radio.value = `${config.variable}-${config.period}`;
            radio.checked = config.checked;
            radio.className = 'layer-radio-hidden';

            const nameSpan = document.createElement('span');
            nameSpan.textContent = config.name;

            label.appendChild(radio);
            label.appendChild(nameSpan);
            grid.appendChild(label);

            radio.addEventListener('change', updateVisibleLayer);
        });

        layerGroupsContainer.appendChild(grid);
        updateVisibleLayer();
    }

    function updateVisibleLayer() {
        const selectedRadio = document.querySelector('input[name="layer-selection"]:checked');
        if (!selectedRadio) return;

        const [variable, period] = selectedRadio.value.split('-');
        
        // Ocultar todas las capas
        Object.values(geeLayers).forEach(variableLayers => {
            Object.values(variableLayers).forEach(layer => {
                if (map.hasLayer(layer)) map.removeLayer(layer);
            });
        });

        // Mostrar solo la capa seleccionada
        if (geeLayers[variable] && geeLayers[variable][period]) {
            map.addLayer(geeLayers[variable][period]);
        }
    }

    function updateDashboard(data) {
        const format = (val, dec=2, unit='') => (val !== null && val !== undefined) ? `${parseFloat(val).toFixed(dec)}${unit}` : 'N/A';
        const change = data.comparativo.cambio_ndvi.valor;
        const changeClass = change > 0.01 ? 'up' : change < -0.01 ? 'down' : '';
        const changeSign = change > 0 ? '+' : '';

        keyMetricsContainer.innerHTML = `
            <div class="metric-card">
                <div class="metric-card-header"><span>🌿 NDVI Actual</span></div>
                <div class="metric-card-body"><div class="value">${format(data.actual.ndvi.valor, 3)}</div></div>
            </div>
            <div class="metric-card">
                <div class="metric-card-header"><span>🔥 Temp. Actual</span></div>
                <div class="metric-card-body"><div class="value">${format(data.actual.temperatura.valor, 1, ' °C')}</div></div>
            </div>
            <div class="metric-card">
                <div class="metric-card-header"><span>💧 Precip. Actual</span></div>
                <div class="metric-card-body"><div class="value">${format(data.actual.precipitacion.valor, 1, ' mm')}</div></div>
            </div>
            <div class="metric-card">
                <div class="metric-card-header"><span>📈 Cambio NDVI</span></div>
                <div class="metric-card-body"><div class="value ${changeClass}">${changeSign}${format(change, 3)}</div></div>
            </div>
        `;

        detailedDashboardContainer.innerHTML = `
            <div class="result-card">
                <h3>Análisis de Vegetación</h3>
                <p class="valor">${format(data.actual.ndvi.valor, 3)} <span class="interpretacion">(NDVI Actual)</span></p>
                <p class="valor">${format(data.comparativo.ndvi_historico.valor, 3)} <span class="interpretacion">(NDVI Histórico)</span></p>
                <p class="valor ${changeClass}">${changeSign}${format(data.comparativo.cambio_ndvi.valor, 3)} <span class="interpretacion">(${data.comparativo.cambio_ndvi.interpretacion})</span></p>
            </div>
             <div class="result-card">
                <h3>Análisis de Temperatura</h3>
                <p class="valor">${format(data.actual.temperatura.valor, 1, ' °C')} <span class="interpretacion">(Temp. Actual)</span></p>
                <p class="valor">${format(data.comparativo.temperatura_historica.valor, 1, ' °C')} <span class="interpretacion">(Temp. Histórica)</span></p>
                <p class="valor ${data.comparativo.cambio_temperatura.valor > 0 ? 'down' : 'up'}">${format(data.comparativo.cambio_temperatura.valor, 1, ' °C')} <span class="interpretacion">(${data.comparativo.cambio_temperatura.interpretacion})</span></p>
            </div>
             <div class="result-card">
                <h3>Análisis de Precipitación</h3>
                <p class="valor">${format(data.actual.precipitacion.valor, 1, ' mm')} <span class="interpretacion">(Precip. Actual)</span></p>
                <p class="valor">${format(data.comparativo.precipitacion_historica.valor, 1, ' mm')} <span class="interpretacion">(Precip. Histórica)</span></p>
                <p class="valor ${data.comparativo.cambio_precipitacion_rel.valor > 0 ? 'up' : 'down'}">${format(data.comparativo.cambio_precipitacion_rel.valor * 100, 0, '%')} <span class="interpretacion">(${data.comparativo.cambio_precipitacion_rel.interpretacion})</span></p>
            </div>
        `;
    }
});
