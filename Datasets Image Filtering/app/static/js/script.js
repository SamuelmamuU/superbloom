document.addEventListener('DOMContentLoaded', () => {

    const form = document.getElementById('analysis-form');
    const loadingIndicator = document.getElementById('loading');
    const resultsContainer = document.getElementById('results-container');
    const submitButton = document.getElementById('submit-button');

    form.addEventListener('submit', async (event) => {
        event.preventDefault(); // Evita que la página se recargue

        // 1. Mostrar el indicador de carga y limpiar resultados anteriores
        loadingIndicator.classList.remove('hidden');
        resultsContainer.innerHTML = '';
        submitButton.disabled = true;

        // 2. Recopilar los datos del formulario
        const xmin = parseFloat(document.getElementById('xmin').value);
        const ymin = parseFloat(document.getElementById('ymin').value);
        const xmax = parseFloat(document.getElementById('xmax').value);
        const ymax = parseFloat(document.getElementById('ymax').value);
        
        const data = {
            coords: [xmin, ymin, xmax, ymax],
            start_date: document.getElementById('start-date').value,
            end_date: document.getElementById('end-date').value
        };

        try {
            // 3. Enviar los datos al backend (Flask)
            const response = await fetch('/analizar', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Error en la respuesta del servidor.');
            }
            
            // 4. Recibir y procesar la respuesta
            const results = await response.json();
            displayResults(results);

        } catch (error) {
            displayError(error.message);
        } finally {
            // 5. Ocultar el indicador de carga al finalizar
            loadingIndicator.classList.add('hidden');
            submitButton.disabled = false;
        }
    });

    function displayResults(data) {
        // Formatear los valores a 4 decimales si existen
        const formatValue = (val) => (val !== null && val !== undefined) ? parseFloat(val).toFixed(4) : 'N/A';

        const indices = data.resultados_calculados.indices;
        
        resultsContainer.innerHTML = `
            <h2>Resultados del Análisis</h2>
            <div class="results-grid">
                <div class="result-card">
                    <h3>NDVI</h3>
                    <p class="valor">${formatValue(indices.ndvi.valor)}</p>
                    <p class="interpretacion">${indices.ndvi.interpretacion}</p>
                </div>
                <div class="result-card">
                    <h3>EVI</h3>
                    <p class="valor">${formatValue(indices.evi.valor)}</p>
                    <p class="interpretacion">${indices.evi.interpretacion}</p>
                </div>
                <div class="result-card">
                    <h3>Índice Floral (NDSI)</h3>
                    <p class="valor">${formatValue(indices.ndsi_floral.valor)}</p>
                    <p class="interpretacion">${indices.ndsi_floral.interpretacion}</p>
                </div>
                <div class="result-card">
                    <h3>Temperatura (LST)</h3>
                    <p class="valor">${formatValue(indices.lst_celsius.valor)} °C</p>
                    <p class="interpretacion">${indices.lst_celsius.interpretacion}</p>
                </div>
            </div>
        `;
    }

    function displayError(message) {
        resultsContainer.innerHTML = `<div class="error-message"><strong>Error:</strong> ${message}</div>`;
    }
});