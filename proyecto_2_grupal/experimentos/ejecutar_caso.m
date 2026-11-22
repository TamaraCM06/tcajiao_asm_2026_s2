% Abre una sesion manual de captura; devuelve enviar, estado y cerrar como operaciones.
function sesion = ejecutar_caso(puerto, nombre, parametros)
    arguments
        puerto (1,1) string
        nombre (1,1) string
        parametros (1,1) struct
    end
    campos = {'periodo_ms', 'duracion_ms', 'timeout_ms'};
    if ~all(isfield(parametros, campos)), error('ASM:Parametros', 'Faltan periodo_ms, duracion_ms o timeout_ms.'); end
    for indiceCampo = 1:numel(campos)
        validateattributes(parametros.(campos{indiceCampo}), {'numeric'}, {'scalar','real','finite','integer','positive'});
    end
    if parametros.periodo_ms < 10 || parametros.periodo_ms > 60000 || ...
            parametros.duracion_ms < parametros.periodo_ms || parametros.duracion_ms > 3600000 || parametros.timeout_ms > 60000
        error('ASM:Tiempos', 'Tiempos fuera del intervalo admitido por el firmware.');
    end
    directorio = fullfile(fileparts(mfilename('fullpath')), 'datos');
    registro = captura.Registro(directorio, nombre, parametros);
    conexion = [];
    vigilancia = [];
    cerrada = false;
    inicioPC = [];
    inicioPendiente = false;
    stopPorTimeout = false;
    try
        conexion = serialport(puerto, 115200, Timeout=2);
        configureTerminator(conexion, 'LF');
        flush(conexion);
        esperarRespuesta('STATUS', 'estado');
        esperarRespuesta(sprintf('CONFIG %d %d %d', parametros.periodo_ms, parametros.duracion_ms, parametros.timeout_ms), 'ok');
        configureCallback(conexion, 'terminator', @recibir);
        vigilancia = timer(ExecutionMode='fixedSpacing', Period=1, TimerFcn=@vigilar);
        start(vigilancia);
    catch excepcion
        cerrar();
        rethrow(excepcion);
    end
    sesion = struct('enviar', @enviar, 'estado', @estado, 'cerrar', @cerrar);
    fprintf('Sesion lista. Ordena FRENO con el angulo liberado, MOTOR con el impulso y START.\n');
    fprintf('Durante captura puedes enviar FRENO o STOP. CSV: %s\n', registro.RutaCSV);

    % Espera una respuesta identificable tras abrir la placa, que puede reiniciarse por USB.
    function esperarRespuesta(comando, tipo)
        inicioEspera = tic;
        ultimoEnvio = -1;
        while toc(inicioEspera) < 8
            if toc(inicioEspera) - ultimoEnvio >= 0.5
                writeline(conexion, comando);
                ultimoEnvio = toc(inicioEspera);
            end
            if conexion.NumBytesAvailable > 0
                linea = char(readline(conexion));
                if startsWith(strtrim(linea), '# ')
                    try
                        mensaje = jsondecode(strtrim(linea(3:end)));
                    catch
                        continue;
                    end
                    if isfield(mensaje, 'tipo') && strcmp(mensaje.tipo, 'error')
                        error('ASM:Rechazo', 'ESP32 rechazo el comando: %s', mensaje.motivo);
                    end
                    if isfield(mensaje, 'tipo') && strcmp(mensaje.tipo, tipo)
                        if strcmp(tipo, 'estado') && ~isfield(mensaje, 'hardware_listo'), continue; end
                        if strcmp(tipo, 'ok') && (~isfield(mensaje, 'comando') || ~strcmp(mensaje.comando, 'CONFIG')), continue; end
                        return;
                    end
                end
            end
            pause(0.02);
        end
        error('ASM:Conexion', 'No se recibio respuesta ASM2; revisa puerto, firmware y monitor serial cerrado.');
    end

    % Envia una sola orden; la ESP32 valida estado, limites y calibracion.
    function enviar(comando)
        if cerrada, error('ASM:Cerrada', 'La sesion esta cerrada.'); end
        comando = char(string(comando));
        if isempty(comando) || length(comando) >= 128 || any(comando < 32 | comando > 126)
            error('ASM:Comando', 'Envia una sola linea ASCII de menos de 128 caracteres.');
        end
        if registro.Finalizado && strcmp(strtrim(comando), 'START')
            error('ASM:Finalizado', 'Abre otra sesion con nombre nuevo para el siguiente ensayo.');
        end
        if strcmp(strtrim(comando), 'START')
            inicioPC = tic;
            inicioPendiente = true;
        end
        writeline(conexion, comando);
    end

    % Procesa una linea completa por callback, guardando las muestras directamente en disco.
    function recibir(origen, ~)
        try
            linea = char(readline(origen));
            estabaActivo = registro.Activo;
            registro.procesar(linea);
            if registro.Activo && ~estabaActivo, inicioPC = tic; inicioPendiente = false; end
            if startsWith(strtrim(linea), '# ')
                mensaje = jsondecode(strtrim(linea(3:end)));
                if inicioPendiente && strcmp(mensaje.tipo, 'error')
                    inicioPendiente = false;
                    inicioPC = [];
                end
            end
            if startsWith(strtrim(linea), '# '), fprintf('%s\n', strtrim(linea)); end
            if registro.Finalizado && ~isempty(vigilancia), stop(vigilancia); end
        catch excepcion
            try
                writeline(conexion, 'STOP');
            catch
            end
            registro.cerrar(['error_recepcion: ' excepcion.message]);
            if ~isempty(vigilancia), stop(vigilancia); end
            warning('ASM:Recepcion', '%s', excepcion.message);
        end
    end

    % Detecta falta de cierre sin depender de que lleguen nuevas lineas del puerto.
    function vigilar(~, ~)
        if cerrada || registro.Finalizado || isempty(inicioPC), return; end
        if inicioPendiente && toc(inicioPC) > 5
            try
                writeline(conexion, 'STOP');
            catch
            end
            registro.cerrar('timeout_sin_inicio');
            stop(vigilancia);
            warning('ASM:Incompleta', 'START no recibio inicio de captura.');
            return;
        end
        duracionMs = parametros.duracion_ms;
        if isfield(registro.Metadatos.configuracion, 'ensayo')
            duracionMs = registro.Metadatos.configuracion.ensayo.duracion_ms;
        end
        if toc(inicioPC) > duracionMs / 1000 + 5 && ~stopPorTimeout
            stopPorTimeout = true;
            try
                writeline(conexion, 'STOP');
            catch
            end
        elseif toc(inicioPC) > duracionMs / 1000 + 8
            registro.cerrar('timeout_sin_fin');
            stop(vigilancia);
            warning('ASM:Incompleta', 'Captura incompleta: no llego el cierre del firmware.');
        end
    end

    % Expone rutas y metadatos sin mantener todas las muestras en RAM.
    function resultado = estado()
        resultado = struct('csv', registro.RutaCSV, 'json', registro.RutaMetadatos, ...
            'activo', registro.Activo, 'finalizado', registro.Finalizado, 'metadatos', registro.Metadatos);
    end

    % Solicita STOP y libera puerto y timer; conserva archivos parciales si no llega fin.
    function cerrar()
        if cerrada, return; end
        if ~isempty(conexion)
            try
                writeline(conexion, 'STOP');
                inicioCierre = tic;
                while registro.Activo && toc(inicioCierre) < 2, pause(0.05); end
                configureCallback(conexion, 'off');
            catch
            end
        end
        cerrada = true;
        if ~isempty(vigilancia), stop(vigilancia); delete(vigilancia); vigilancia = []; end
        registro.cerrar('cierre_pc_sin_fin');
        conexion = [];
    end
end
