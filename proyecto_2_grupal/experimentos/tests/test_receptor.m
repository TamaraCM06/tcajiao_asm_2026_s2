% Comprueba el receptor con tramas simuladas; no abre puertos ni acredita hardware.
function pruebas = test_receptor
    pruebas = functiontests(localfunctions);
end

% Agrega el paquete del receptor sin depender del directorio de trabajo.
function setupOnce(caso)
    caso.TestData.pathAnterior = path;
    addpath(fileparts(fileparts(mfilename('fullpath'))));
end

% Devuelve el path al estado previo de MATLAB.
function teardownOnce(caso)
    path(caso.TestData.pathAnterior);
end

% Crea archivos temporales separados para cada ensayo simulado.
function registro = crearRegistro()
    registro = captura.Registro(tempname, 'simulado', struct('origen', 'prueba_sin_hardware'));
end

% Genera una trama completa con dos filas y todos los grupos de configuracion.
function lineas = tramaBase()
    lineas = [
        "# {""tipo"":""inicio"",""protocolo"":1,""ensayo"":1,""firmware"":""simulacion""}"
        "# {""tipo"":""configuracion"",""grupo"":""ensayo"",""periodo_ms"":20,""duracion_ms"":100,""timeout_ms"":300}"
        "# {""tipo"":""configuracion"",""grupo"":""sensor"",""pulsos_por_vuelta"":24}"
        "# {""tipo"":""configuracion"",""grupo"":""servo"",""liberado_deg"":10}"
        "# {""tipo"":""configuracion"",""grupo"":""motor"",""maximo_porcentaje"":30}"
        "tiempo_ms,freno_deg,velocidad_rpm"
        "0.000,10.000,1000.000"
        "20.000,40.000,950.000"
        "# {""tipo"":""fin"",""ensayo"":1,""completo"":true,""producidas"":2,""enviadas"":2,""vencimientos_perdidos"":0}"
    ];
end

% Reproduce lineas en el mismo interpretador utilizado por el callback serial.
function entregar(registro, lineas)
    for indiceLinea = 1:numel(lineas), registro.procesar(lineas(indiceLinea)); end
end

% Verifica cabecera exacta, valores sin transformacion y metadatos separados.
function testCSVCompleto(caso)
    registro = crearRegistro();
    entregar(registro, tramaBase());
    verifyTrue(caso, registro.Finalizado && registro.Metadatos.completo);
    tabla = readtable(registro.RutaCSV);
    verifyEqual(caso, tabla.Properties.VariableNames, {'tiempo_ms','freno_deg','velocidad_rpm'});
    verifyEqual(caso, tabla.tiempo_ms, [0;20]);
    verifyEqual(caso, tabla.freno_deg, [10;40]);
    metadatos = jsondecode(fileread(registro.RutaMetadatos));
    verifyEqual(caso, metadatos.muestras_recibidas, 2);
end

% Un cierre ausente debe conservar los archivos y marcar captura incompleta.
function testSinCierre(caso)
    registro = crearRegistro(); lineas = tramaBase();
    entregar(registro, lineas(1:end-1)); registro.cerrar('timeout_sin_fin');
    verifyFalse(caso, registro.Metadatos.completo);
    verifyEqual(caso, registro.Metadatos.muestras_recibidas, 2);
end

% Un conteo alterado no puede acreditar una captura completa.
function testConteoIncompatible(caso)
    registro = crearRegistro(); lineas = tramaBase();
    lineas(end) = replace(lineas(end), '"enviadas":2', '"enviadas":3');
    entregar(registro, lineas);
    verifyFalse(caso, registro.Metadatos.completo);
end

% El tiempo debe aumentar; repetir una fila no sustituye una muestra perdida.
function testTiempoRepetido(caso)
    registro = crearRegistro(); lineas = tramaBase(); lineas(8) = lineas(7);
    entregar(registro, lineas);
    verifyFalse(caso, registro.Metadatos.completo);
    verifyEqual(caso, registro.Metadatos.filas_invalidas, 1);
end

% NaN en velocidad conserva la falta de informacion sin convertirla a cero.
function testVelocidadDesconocida(caso)
    registro = crearRegistro(); lineas = tramaBase(); lineas(8) = "20.000,40.000,nan";
    entregar(registro, lineas);
    verifyTrue(caso, registro.Metadatos.completo);
    tabla = readtable(registro.RutaCSV);
    verifyTrue(caso, isnan(tabla.velocidad_rpm(2)));
end

% Una linea ajena intercalada invalida el transporte, aunque lleguen las filas esperadas.
function testTextoIntercalado(caso)
    registro = crearRegistro(); lineas = tramaBase();
    entregar(registro, [lineas(1:7); "mensaje ajeno"; lineas(8:end)]);
    verifyFalse(caso, registro.Metadatos.completo);
end

% Faltar un grupo de configuracion impide declarar reproducibilidad de la captura.
function testConfiguracionIncompleta(caso)
    registro = crearRegistro(); lineas = tramaBase(); lineas(5) = [];
    entregar(registro, lineas);
    verifyFalse(caso, registro.Metadatos.completo);
end

% Un reinicio y un inicio nuevo en mitad del ensayo no reemplazan el origen anterior.
function testInicioDuplicado(caso)
    registro = crearRegistro(); lineas = tramaBase();
    entregar(registro, [lineas(1:7); lineas(1); lineas(8:end)]);
    verifyFalse(caso, registro.Metadatos.completo);
end

% Un nombre existente se conserva incluso si el ensayo previo quedo incompleto.
function testNoSobrescribir(caso)
    directorio = tempname;
    registro = captura.Registro(directorio, 'mismo', struct()); registro.cerrar('prueba');
    verifyError(caso, @() captura.Registro(directorio, 'mismo', struct()), 'ASM:Existe');
end

% Contrasta el receptor con mensajes realmente formateados por el coordinador C en PC.
function testTramaProduccionC(caso)
    carpetaProyecto = fileparts(fileparts(fileparts(mfilename('fullpath'))));
    ruta = fullfile(carpetaProyecto, 'firmware', 'build', 'pruebas', 'trama_produccion.txt');
    assumeTrue(caso, isfile(ruta), 'Ejecuta primero pytest del firmware para generar la trama C.');
    registro = crearRegistro(); entregar(registro, splitlines(string(fileread(ruta))));
    verifyTrue(caso, registro.Metadatos.completo);
    verifyEqual(caso, registro.Metadatos.muestras_recibidas, 3);
end
