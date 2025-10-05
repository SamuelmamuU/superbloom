document.addEventListener('DOMContentLoaded', () => {

    // --- CONFIGURACIÓN ---
    const MAPBOX_TOKEN = 'sk.eyJ1Ijoic2FtdW1hbXUiLCJhIjoiY21nY3pndHRsMHZjNzJsbzd3YmRnZ3k2aCJ9.IN5gKsMsEjaejKJEALxB_A'; // <-- REEMPLAZA ESTO
    const MAPBOX_STYLE_URL = `https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`;
    const MAPBOX_ATTRIBUTION = '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a>';

    // --- ELEMENTOS DEL DOM ---
    const form = document.getElementById('analysis-form');
    const submitButton = document.getElementById('submit-button');
    const loadingIndicator = document.getElementById('loading');
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    const dashboardCardsContainer = document.getElementById('dashboard-cards');

    // --- ESTADO DE LA APLICACIÓN ---
    let map;
    let layerControl;
    let geeLayers = {}; // Objeto para guardar las capas de GEE

    // ===========================================
    // 1. INICIALIZACIÓN DEL MAPA
    // ===========================================
    function initMap() {
        map = L.map('map').setView([32.62, -115.46], 10); // Coordenadas iniciales

        L.tileLayer(MAPBOX_STYLE_URL, {
            attribution: MAPBOX_ATTRIBUTION,
            tileSize: 512,
            zoomOffset: -1
        }).addTo(map);

        layerControl = L.control.layers(null, null, { collapsed: false }).addTo(map);
    }
    
    initMap(); // Inicializa el mapa al cargar la página

    // ===========================================
    // 2. LÓGICA DE LAS PESTAÑAS (TABS)
    // ===========================================
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Desactivar todos
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Activar el seleccionado
            button.classList.add('active');
            document.getElementById(button.dataset.tab).classList.add('active');
        });
    });

    // ===========================================
    // 3. MANEJO DEL FORMULARIO Y LLAMADA A LA API
    // ===========================================
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        // --- UI y Recopilación de datos ---
        submitButton.disabled = true;
        loadingIndicator.classList.remove('hidden');
        dashboardCardsContainer.innerHTML = '<p class="placeholder">Procesando nuevos datos...</p>';

        const xmin = parseFloat(document.getElementById('xmin').value);
        const ymin = parseFloat(document.getElementById('ymin').value);
        const xmax = parseFloat(document.getElementById('xmax').value);
        const ymax = parseFloat(document.getElementById('ymax').value);
        
        const payload = {
            coords: [xmin, ymin, xmax, ymax],
            historic_start: document.getElementById('historic-start').value,
            historic_end: document.getElementById('historic-end').value,
            current_start: document.getElementById('current-start').value,
            current_end: document.getElementById('current-end').value
        };

        // --- Llamada a la API de Flask ---
        try {
            const response = await fetch('/analizar-ecosistema', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Error desconocido del servidor.');
            }

            const results = await response.json();

            // --- Actualizar la UI con los resultados ---
            updateMap(results.map_data);
            updateDashboard(results.dashboard_data);

        } catch (error) {
            dashboardCardsContainer.innerHTML = `<p class="placeholder" style="color: red;"><strong>Error:</strong> ${error.message}</p>`;
            console.error("Error en el análisis:", error);
        } finally {
            submitButton.disabled = false;
            loadingIndicator.classList.add('hidden');
        }
    });

    // ===========================================
    // 4. FUNCIONES DE ACTUALIZACIÓN DE LA UI
    // ===========================================
    function updateMap(mapData) {
        // --- Limpiar capas anteriores del mapa y del control ---
        Object.values(geeLayers).forEach(layer => {
            if (map.hasLayer(layer)) {
                layerControl.removeLayer(layer);
                map.removeLayer(layer);
            }
        });

        // --- Crear y añadir nuevas capas ---
        geeLayers.historico = L.tileLayer(mapData.tile_urls.historico, { opacity: 0.7 });
        geeLayers.actual = L.tileLayer(mapData.tile_urls.actual, { opacity: 0.7 });
        geeLayers.diferencia = L.tileLayer(mapData.tile_urls.diferencia, { opacity: 0.7 });

        layerControl.addOverlay(geeLayers.historico, 'NDVI Histórico');
        layerControl.addOverlay(geeLayers.actual, 'NDVI Actual');
        layerControl.addOverlay(geeLayers.diferencia, 'Contraste NDVI');

        // Por defecto, mostrar la capa de contraste
        geeLayers.diferencia.addTo(map);

        // --- Centrar el mapa en la nueva región ---
        map.flyTo(mapData.centro, 10);
    }

    function updateDashboard(dashboardData) {
        const formatValue = (val) => (val !== null && val !== undefined) ? parseFloat(val).toFixed(4) : 'N/A';
        
        dashboardCardsContainer.innerHTML = `
            <div class="result-card">
                <h3>NDVI Histórico (Promedio)</h3>
                <p class="valor">${formatValue(dashboardData.ndvi_historico)}</p>
                <p class="interpretacion">Valor base para la comparación.</p>
            </div>
            <div class="result-card">
                <h3>NDVI Actual (Promedio)</h3>
                <p class="valor">${formatValue(dashboardData.ndvi_actual)}</p>
                <p class="interpretacion">Salud actual de la vegetación.</p>
            </div>
            <div class="result-card">
                <h3>Cambio Neto de NDVI</h3>
                <p class="valor">${formatValue(dashboardData.cambio_ndvi)}</p>
                <p class="interpretacion">${dashboardData.interpretacion}</p>
            </div>
        `;
    }
});