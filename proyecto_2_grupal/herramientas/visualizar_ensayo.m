% 1. Seleccionar una captura con tiempo_ms, freno_deg y velocidad_rpm.
carpeta = fileparts(mfilename('fullpath'));
carpeta_datos = fullfile(carpeta, '..', 'experimentos', 'datos');
[nombre_csv, ruta_csv] = uigetfile(fullfile(carpeta_datos, '*.csv'), 'Seleccionar ensayo de frenado');
if isequal(nombre_csv, 0)
    return
end
datos = readtable(fullfile(ruta_csv, nombre_csv));

% 2. Usar segundos en ambas gráficas.
tiempo_s = datos.tiempo_ms / 1000;

% 3. Comparar el mando del freno con la velocidad del disco.
figure('Name', char(nombre_csv), 'NumberTitle', 'off');
tiledlayout(2, 1);
eje_freno = nexttile;
stairs(tiempo_s, datos.freno_deg, 'LineWidth', 1.5);
ylabel('Mando del freno (°)');
title('Entrada al servo');
grid on;

eje_velocidad = nexttile;
plot(tiempo_s, datos.velocidad_rpm, '.-', 'LineWidth', 1.5);
ylabel('Velocidad (RPM)');
xlabel('Tiempo (s)');
title('Respuesta del disco');
grid on;
linkaxes([eje_freno, eje_velocidad], 'x');

% 4. Medir un único escalón y el cambio observado hasta la última muestra.
cambios = find(diff(datos.freno_deg) ~= 0);
if numel(cambios) ~= 1
    warning('Para medir el escalón, el registro debe contener un solo cambio de mando.');
    return
end
antes = cambios(1);  % Última muestra con la orden original.
despues = antes + 1;
t_escalon = tiempo_s(despues);
delta_grados = datos.freno_deg(despues) - datos.freno_deg(antes);
rpm_inicial = mean(datos.velocidad_rpm(1:antes));
delta_rpm = datos.velocidad_rpm(end) - rpm_inicial;

xline(eje_velocidad, t_escalon, '--', 'Orden de freno');
fprintf('Escalón en %.3f s, cambio de mando: %+.1f grados\n', t_escalon, delta_grados);
fprintf('RPM iniciales (promedio): %.2f | Última muestra: %.2f RPM\n', ...
    rpm_inicial, datos.velocidad_rpm(end));
fprintf('Cambio observado: %+.2f RPM (%+.2f RPM/grado)\n', delta_rpm, delta_rpm / delta_grados);

% 5. Estimar pendientes locales alrededor de la orden, con el motor apagado.
ventana_ms = 300;  % Ajustable según el muestreo y la duración del frenado.
ms_desde_orden = datos.tiempo_ms - datos.tiempo_ms(despues);
en_movimiento = datos.velocidad_rpm > 0;
previas = ms_desde_orden >= -ventana_ms & ms_desde_orden < 0 & en_movimiento;
posteriores = ms_desde_orden >= 0 & ms_desde_orden <= ventana_ms & en_movimiento;
if any(diff(tiempo_s) <= 0) || nnz(previas) < 2 || nnz(posteriores) < 2
    warning('Se necesitan tiempos crecientes y al menos dos muestras en movimiento por tramo.');
    return
end

% El primer coeficiente de cada recta es su pendiente en RPM/s.
recta_antes = polyfit(tiempo_s(previas), datos.velocidad_rpm(previas), 1);
recta_despues = polyfit(tiempo_s(posteriores), datos.velocidad_rpm(posteriores), 1);
fprintf('Pendiente antes: %+.1f RPM/s | después: %+.1f RPM/s\n', ...
    recta_antes(1), recta_despues(1));

hold(eje_velocidad, 'on');
trazo_antes = plot(eje_velocidad, tiempo_s(previas), ...
    polyval(recta_antes, tiempo_s(previas)), 'o--');
trazo_despues = plot(eje_velocidad, tiempo_s(posteriores), ...
    polyval(recta_despues, tiempo_s(posteriores)), 's--');
legend(eje_velocidad, [trazo_antes, trazo_despues], 'Ajuste antes', 'Ajuste después');
hold(eje_velocidad, 'off');

% 6. Modelo local: el escalón cambia gradualmente la pendiente de las RPM.
% Ajustar desde la orden hasta la última muestra anterior a la detención.
fin = find(datos.velocidad_rpm(despues:end) <= 0, 1);
if isempty(fin)
    tramo = despues:height(datos);
else
    tramo = despues:(despues + fin - 2);
end
if numel(tramo) < 4
    warning('El ajuste necesita la muestra de la orden y tres posteriores en movimiento.');
    return
end
t = tiempo_s(tramo) - t_escalon;
rpm_medidas = datos.velocidad_rpm(tramo);
rpm_libres = rpm_medidas(1) + recta_antes(1) * t;
efecto_medido = rpm_medidas - rpm_libres;

% Para cada tau, integrar una aceleración de primer orden y ajustar su amplitud.
% expm1(x) calcula exp(x)-1 con precisión cerca de cero.
forma = @(tau) t + tau * expm1(-t / tau);
amplitud = @(f) (f' * efecto_medido) / (f' * f);
error_ajuste = @(f) sum((efecto_medido - amplitud(f) * f).^2);
tau_min = min(diff(t)) / 100;
tau_max = 10 * t(end);
tau = exp(fminbnd(@(log_tau) error_ajuste(forma(exp(log_tau))), ...
    log(tau_min), log(tau_max)));
f = forma(tau);
cambio_pendiente = amplitud(f);
K = cambio_pendiente / delta_grados;  % (RPM/s) por grado de mando
rpm_modelo = rpm_libres + cambio_pendiente * f;
rmse = sqrt(mean((rpm_modelo - rpm_medidas).^2));

hold(eje_velocidad, 'on');
trazo_modelo = plot(eje_velocidad, tiempo_s(tramo), rpm_modelo, '-', ...
    'Color', [1.00 0.84 0.25], 'LineWidth', 1.5);
legend(eje_velocidad, [trazo_antes, trazo_despues, trazo_modelo], ...
    'Ajuste antes', 'Ajuste después', 'Modelo de velocidad');
hold(eje_velocidad, 'off');
fprintf('Modelo local: K = %.2f (RPM/s)/grado | tau = %.3f s | RMSE = %.2f RPM\n', ...
    K, tau, rmse);
if tau < median(diff(t)) || tau > t(end)
    fprintf('La escala de tiempo estimada queda fuera de la resolución típica o duración del tramo.\n');
end

% 7. Impulso del mando al cambio de RPM respecto a la caída libre.
% La aceleración responde como K/(tau*s+1). Integrarla da la velocidad:
% G(s) = K / (s*(tau*s+1)). tf e impulse usan Control System Toolbox.
t_impulso = linspace(0, t(end), 501);
if ~isempty(ver('control')) && license('test', 'Control_Toolbox')
    modelo_velocidad = tf(K, [tau 1 0]);
    [delta_rpm_impulso, t_impulso] = impulse(modelo_velocidad, t_impulso);
    fprintf('Respuesta al impulso calculada con impulse (Control System Toolbox).\n');
else
    % Transformada inversa de G(s): h(t) = K*(1-exp(-t/tau)) para t >= 0.
    delta_rpm_impulso = -K * expm1(-t_impulso / tau);
    fprintf('Respuesta al impulso calculada con la fórmula analítica del modelo.\n');
end

figure('Name', 'Respuesta al impulso del modelo', 'NumberTitle', 'off');
plot(t_impulso, delta_rpm_impulso, 'Color', [1.00 0.84 0.25], 'LineWidth', 1.5);
xlabel('Tiempo desde el impulso (s)');
ylabel('Cambio de velocidad (RPM)');
title('Impulso de freno de área 1 grado·s');
grid on;
