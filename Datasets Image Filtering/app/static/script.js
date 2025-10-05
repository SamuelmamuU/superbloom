document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('config-form');
    const imagenContainer = document.getElementById('imagen-container');
    const loading = document.getElementById('loading');
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Mostrar indicador de carga
        loading.classList.remove('hidden');
        imagenContainer.innerHTML = '';
        
        // Obtener datos del formulario
        const formData = new FormData(form);
        
        // Enviar solicitud al servidor
        fetch('/generar-imagen', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Error al generar la imagen');
            }
            return response.blob();
        })
        .then(blob => {
            // Crear URL para la imagen
            const imageUrl = URL.createObjectURL(blob);
            
            // Mostrar imagen
            const img = document.createElement('img');
            img.src = imageUrl;
            imagenContainer.appendChild(img);
            
            // Ocultar indicador de carga
            loading.classList.add('hidden');
        })
        .catch(error => {
            console.error('Error:', error);
            imagenContainer.innerHTML = `<p class="error">Error: ${error.message}</p>`;
            loading.classList.add('hidden');
        });
    });
});