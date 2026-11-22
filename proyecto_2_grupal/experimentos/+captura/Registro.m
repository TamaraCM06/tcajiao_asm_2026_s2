% Conserva muestras en disco y valida el cierre del protocolo ASM2 de captura.
classdef Registro < handle
    properties (SetAccess = private)
        RutaCSV
        RutaMetadatos
        Activo = false
        Finalizado = false
        Metadatos
    end
    properties (Access = private)
        Archivo = -1
        Cabecera = false
        UltimoTiempo = -1
        Cantidad = 0
        FilasInvalidas = 0
    end
    methods
        % Reserva un nombre nuevo y registra que todavia no existe un ensayo completo.
        function objeto = Registro(directorio, nombre, parametros)
            if isempty(regexp(char(nombre), '^[A-Za-z0-9_-]+$', 'once'))
                error('ASM:Nombre', 'Usa un identificador con letras, numeros, guion o guion bajo.');
            end
            if ~isfolder(directorio), mkdir(directorio); end
            objeto.RutaCSV = fullfile(directorio, char(nombre) + ".csv");
            objeto.RutaMetadatos = fullfile(directorio, char(nombre) + ".json");
            if isfile(objeto.RutaCSV) || isfile(objeto.RutaMetadatos)
                error('ASM:Existe', 'El identificador ya existe; no se sobrescriben ensayos.');
            end
            objeto.Metadatos = struct('protocolo', 1, 'fecha_pc', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')),...
                'matlab', version, 'solicitada', parametros, 'configuracion', struct(),...
                'eventos', {{}}, 'errores', {{}}, 'completo', false, 'estado', 'esperando_inicio');
            objeto.Archivo = fopen(objeto.RutaCSV, 'w', 'n', 'UTF-8');
            if objeto.Archivo < 0, error('ASM:Archivo', 'No se pudo crear el CSV.'); end
            objeto.guardarMetadatos();
        end

        % Separa metadatos JSON y las tres columnas; no calcula modelos ni h(t).
        function procesar(objeto, linea)
            if objeto.Finalizado, return; end
            texto = strtrim(char(linea));
            if startsWith(texto, '# ')
                try
                    mensaje = jsondecode(texto(3:end));
                    if ~isstruct(mensaje) || ~isfield(mensaje, 'tipo'), error('ASM:Formato', 'Sin tipo.'); end
                    objeto.procesarMensaje(mensaje);
                catch excepcion
                    objeto.FilasInvalidas = objeto.FilasInvalidas + double(objeto.Activo);
                    objeto.Metadatos.errores{end+1} = struct('motivo', 'metadato_invalido', 'detalle', excepcion.message);
                end
                return;
            end
            if ~objeto.Activo, return; end
            if strcmp(texto, 'tiempo_ms,freno_deg,velocidad_rpm')
                if objeto.Cabecera
                    objeto.FilasInvalidas = objeto.FilasInvalidas + 1;
                else
                    objeto.Cabecera = true;
                    fprintf(objeto.Archivo, '%s\n', texto);
                end
                return;
            end
            columnas = split(string(texto), ',');
            valores = str2double(columnas);
            correcta = objeto.Cabecera && numel(valores) == 3;
            if correcta
                correcta = all(isfinite(valores(1:2))) && valores(1) >= 0 && valores(1) > objeto.UltimoTiempo && ...
                    ((isfinite(valores(3)) && valores(3) >= 0) || strcmpi(columnas(3), 'nan'));
            end
            if ~correcta
                objeto.FilasInvalidas = objeto.FilasInvalidas + 1;
                return;
            end
            fprintf(objeto.Archivo, '%s\n', texto);
            objeto.UltimoTiempo = valores(1);
            objeto.Cantidad = objeto.Cantidad + 1;
        end

        % Conserva un ensayo parcial al cerrar o perder la conexion antes de recibir fin.
        function cerrar(objeto, motivo)
            if objeto.Finalizado, return; end
            objeto.Activo = false;
            objeto.Finalizado = true;
            objeto.Metadatos.estado = char(motivo);
            objeto.Metadatos.completo = false;
            objeto.finalizarArchivos();
        end

        % Cierra archivos aun cuando el llamador elimina el objeto durante un error.
        function delete(objeto)
            if objeto.Archivo >= 0
                objeto.cerrar('objeto_eliminado_sin_fin');
            end
        end
    end
    methods (Access = private)
        % Exige inicio, cabecera y conteos consistentes para aceptar una captura completa.
        function procesarMensaje(objeto, mensaje)
            switch mensaje.tipo
                case 'inicio'
                    if objeto.Activo || mensaje.protocolo ~= 1
                        error('ASM:Inicio', 'Inicio duplicado o version no admitida.');
                    end
                    objeto.Metadatos.inicio = mensaje;
                    objeto.Metadatos.estado = 'capturando';
                    objeto.Activo = true;
                case 'configuracion'
                    if objeto.Activo
                        grupo = char(mensaje.grupo);
                        if ~ismember(grupo, {'ensayo', 'sensor', 'servo', 'motor'})
                            error('ASM:Grupo', 'Grupo desconocido.');
                        end
                        objeto.Metadatos.configuracion.(grupo) = mensaje;
                    end
                case 'evento'
                    if objeto.Activo, objeto.Metadatos.eventos{end+1} = mensaje; end
                case 'error'
                    objeto.Metadatos.errores{end+1} = mensaje;
                case 'fin'
                    if ~objeto.Activo, error('ASM:Fin', 'Cierre sin inicio.'); end
                    grupos = {'ensayo', 'sensor', 'servo', 'motor'};
                    objeto.Metadatos.fin = mensaje;
                    objeto.Metadatos.completo = logical(mensaje.completo) && objeto.Cabecera && ...
                        mensaje.ensayo == objeto.Metadatos.inicio.ensayo && ...
                        mensaje.enviadas == objeto.Cantidad && mensaje.producidas == objeto.Cantidad && ...
                        mensaje.vencimientos_perdidos == 0 && objeto.FilasInvalidas == 0 && ...
                        all(isfield(objeto.Metadatos.configuracion, grupos));
                    objeto.Activo = false;
                    objeto.Finalizado = true;
                    objeto.Metadatos.estado = 'fin_recibido';
                    objeto.finalizarArchivos();
            end
        end

        % Cierra el CSV y deja cantidades reales y problemas de formato en el JSON.
        function finalizarArchivos(objeto)
            if objeto.Archivo >= 0, fclose(objeto.Archivo); objeto.Archivo = -1; end
            objeto.Metadatos.muestras_recibidas = objeto.Cantidad;
            objeto.Metadatos.filas_invalidas = objeto.FilasInvalidas;
            objeto.guardarMetadatos();
        end

        % Escribe metadatos separados para no agregar columnas al CSV del analisis existente.
        function guardarMetadatos(objeto)
            archivoMetadatos = fopen(objeto.RutaMetadatos, 'w', 'n', 'UTF-8');
            if archivoMetadatos < 0, error('ASM:Metadatos', 'No se pudo guardar el JSON.'); end
            limpieza = onCleanup(@() fclose(archivoMetadatos));
            fprintf(archivoMetadatos, '%s\n', jsonencode(objeto.Metadatos, PrettyPrint=true));
        end
    end
end
