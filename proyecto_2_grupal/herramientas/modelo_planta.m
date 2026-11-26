function modelo = modelo_planta(carpeta)
% Modelo de la planta a partir de una campana de banco.py pid (por defecto datos/identificacion).
% Uso: modelo_planta  o  modelo_planta('../datos/identificacion'); tambien: python banco.py modelo
%
% Modelo:  dw/dt = -(c + b*w) - k*max(0, theta - theta_c),  theta sigue la orden con constante tau
%   caida_libre  -> friccion c [RPM/s] y b [1/s]
%   escalones y freno_maximo -> desaceleracion agregada D y tau por ensayo; D contra el angulo da k
%                                [RPM/s por grado] y el angulo de contacto theta_c (zona muerta)
%   validacion   -> prediccion con el modelo final y RMSE (no se usa para ajustar)
% Para el PID (u en [0,1], theta = theta_c + u*(theta_max - theta_c)):
%   G(s) = W(s)/U(s) = -Ku / ((s + b)(tau*s + 1)),   Ku = k*(theta_max - theta_c)
% Resultados en <carpeta>/modelo/: modelo.json, escalones.csv, validacion.csv y figuras PNG.
% Solo funciones base: corre igual en MATLAB y en GNU Octave.

  if nargin < 1
    carpeta = fullfile(fileparts(mfilename('fullpath')), '..', 'datos', 'identificacion');
  end
  if exist('OCTAVE_VERSION', 'builtin') && isempty(getenv('DISPLAY'))
    graphics_toolkit('gnuplot');   % Octave sin pantalla: necesario para guardar las figuras
  end
  salida = fullfile(carpeta, 'modelo');
  if ~exist(salida, 'dir'), mkdir(salida); end
  indice = leer_indice(fullfile(carpeta, 'indice.csv'));
  indice = indice(strcmp({indice.completo}, 'si'));
  config = leer_config(fullfile(carpeta, indice(1).archivo));
  ts = config.ensayo.periodo_ms / 1000;
  liberado = config.servo.liberado_deg;
  maximo = config.servo.maximo_deg;

  % 1. Friccion: pares (velocidad, desaceleracion) de las caidas libres
  [w_libre, a_libre] = pares_indice(carpeta, indice, 'caida_libre');
  p = polyfit(w_libre, a_libre, 1);            % a = c + b*w
  friccion = struct('c', p(2), 'b', max(p(1), 1e-4), 'n', numel(w_libre));
  fprintf('Friccion: c = %.1f RPM/s, b = %.4f 1/s (%d puntos)\n', friccion.c, friccion.b, friccion.n);

  % 2. Escalones (incluye freno maximo): D y tau por ensayo
  grupos = {'escalones', 'freno_maximo'};
  escalones = struct('archivo', {}, 'nivel', {}, 'freno', {}, 'w0', {}, 'D', {}, 'tau', {}, 'rmse', {});
  for i = find(ismember({indice.grupo}, grupos))
    [t, freno, rpm] = leer_ensayo(fullfile(carpeta, indice(i).archivo));
    [D, tau, rmse, w0] = ajustar_escalon(t, freno, rpm, friccion);
    escalones(end + 1) = struct('archivo', indice(i).archivo, 'nivel', indice(i).nivel, ...
                                'freno', freno(end), 'w0', w0, 'D', D, 'tau', tau, 'rmse', rmse);
  end
  angulos = [escalones.freno]; D = [escalones.D];

  % 3. Ganancia del freno y zona muerta: D = k*(theta - theta_c) donde D es claramente positiva
  activos = D > 0.1 * max(D);
  q = polyfit(angulos(activos), D(activos), 1);
  freno = struct('k', q(1), 'contacto', -q(2) / q(1), 'liberado', liberado, 'maximo', maximo, ...
                 'tau', median([escalones(angulos > -q(2) / q(1) + 10).tau]));
  Ku = freno.k * (maximo - freno.contacto);
  fprintf('Freno: k = %.2f RPM/s por grado, contacto = %.1f grados, tau = %.3f s, D max = %.0f RPM/s\n', ...
          freno.k, freno.contacto, freno.tau, Ku);

  % 4. Planta para el PID, continua y discreta (ZOH, Ts)
  polos_s = [-friccion.b, -1 / freno.tau];
  [polos_z, cero_z] = discretizar(Ku / freno.tau, friccion.b, 1 / freno.tau, ts);
  fprintf('G(s) = -%.0f / ((s + %.4f)(%.3f s + 1))  [RPM por unidad de u]\n', Ku, friccion.b, freno.tau);
  fprintf('Ts = %.0f ms: polos z = %.4f, %.4f; cero z = %.4f\n', ts * 1000, polos_z(1), polos_z(2), cero_z);

  % 5. Validacion con ensayos que no se usaron para ajustar
  validacion = struct('archivo', {}, 'freno', {}, 'rmse', {}, 'parada_medida', {}, 'parada_modelo', {});
  figura = nueva_figura();
  validos = find(strcmp({indice.grupo}, 'validacion'));
  for n = 1:numel(validos)
    [t, ang, rpm] = leer_ensayo(fullfile(carpeta, indice(validos(n)).archivo));
    [tt, medido, modelo_w] = predecir(t, ang, rpm, friccion, freno);
    ok = medido > 0;
    validacion(end + 1) = struct('archivo', indice(validos(n)).archivo, 'freno', ang(end), ...
        'rmse', sqrt(mean((medido(ok) - modelo_w(ok)) .^ 2)), ...
        'parada_medida', tiempo_parada(tt, medido), 'parada_modelo', tiempo_parada(tt, modelo_w));
    subplot(ceil(numel(validos) / 2), 2, n);
    plot(tt, medido, '.', tt, modelo_w, '-', 'LineWidth', 1.2); grid on;
    title(indice(validos(n)).archivo, 'Interpreter', 'none', 'FontSize', 8); xlabel('t desde el freno (s)'); ylabel('RPM');
  end
  guardar_figura(figura, fullfile(salida, 'validacion.png'));
  if ~isempty(validacion)
    fprintf('Validacion: RMSE medio %.1f RPM en %d ensayos\n', mean([validacion.rmse]), numel(validacion));
  end

  % 6. Rampas alcanzables: mas rapida que la caida libre, mas lenta que el freno maximo
  niveles = jsondecode(fileread(fullfile(carpeta, 'niveles.json')));
  w_fin = 250;
  rampa = struct();
  for nombre = {'alto', 'bajo'}
    w0 = getfield(niveles.mesetas_rpm, ['x' sprintf('%g', niveles.(nombre{1}))]);
    a_min = friccion.c + friccion.b * w0;              % caida libre a la velocidad inicial
    a_max = friccion.c + friccion.b * w_fin + Ku;      % freno maximo al final de la rampa
    rampa.(nombre{1}) = struct('w0_rpm', w0, 'a_min_rpm_s', a_min, 'a_max_rpm_s', a_max, ...
                               'a_sugerida_rpm_s', (a_min + a_max) / 2);
    fprintf('Rampa %s desde %.0f RPM: entre %.0f y %.0f RPM/s (sugerida %.0f)\n', ...
            nombre{1}, w0, a_min, a_max, (a_min + a_max) / 2);
  end

  % 7. Figuras y archivos
  figura = nueva_figura();
  subplot(1, 2, 1);
  [w_max, a_max_med] = pares_indice(carpeta, indice, 'freno_maximo');
  ww = linspace(0, max([w_libre; w_max]), 50);
  plot(w_libre, a_libre, '.', w_max, a_max_med, '.', ww, friccion.c + friccion.b * ww, '-', ...
       ww, friccion.c + friccion.b * ww + Ku, '-', 'LineWidth', 1.2); grid on;
  xlabel('velocidad (RPM)'); ylabel('desaceleracion (RPM/s)'); legend('caida libre', 'freno maximo', ...
       'modelo friccion', 'modelo freno maximo', 'Location', 'northwest');
  subplot(1, 2, 2);
  aa = linspace(liberado, maximo, 50);
  plot(angulos, D, 'o', aa, freno.k * max(0, aa - freno.contacto), '-', 'LineWidth', 1.2); grid on;
  xlabel('angulo del freno (grados)'); ylabel('desaceleracion agregada D (RPM/s)');
  title(sprintf('k = %.2f RPM/s/grado, contacto %.1f grados', freno.k, freno.contacto));
  guardar_figura(figura, fullfile(salida, 'planta.png'));

  figura = nueva_figura();
  th = linspace(0, 2 * pi, 200);
  plot(cos(th), sin(th), 'k:', real(polos_z), imag(polos_z), 'x', real(cero_z), imag(cero_z), 'o', ...
       'MarkerSize', 10, 'LineWidth', 1.5); axis equal; grid on;
  title(sprintf('Planta discreta, Ts = %.0f ms', ts * 1000)); legend('|z| = 1', 'polos', 'cero');
  guardar_figura(figura, fullfile(salida, 'polos_ceros.png'));

  escribir_tabla(fullfile(salida, 'escalones.csv'), escalones);
  escribir_tabla(fullfile(salida, 'validacion.csv'), validacion);
  modelo = struct('fecha', datestr(now, 'yyyy-mm-ddTHH:MM:SS'), 'ts_s', ts, ...
      'ecuacion', 'dw/dt = -(c + b*w) - k*max(0, theta - theta_c); theta con retardo tau', ...
      'friccion', struct('c_rpm_s', friccion.c, 'b_1_s', friccion.b), ...
      'freno', struct('k_rpm_s_por_grado', freno.k, 'contacto_deg', freno.contacto, ...
                      'liberado_deg', liberado, 'maximo_deg', maximo, 'tau_s', freno.tau), ...
      'pid', struct('entrada', 'u en [0,1]: theta = contacto + u*(maximo - contacto)', ...
                    'G_s', sprintf('-%.4g / ((s + %.4g)(%.4g s + 1)) [RPM]', Ku, friccion.b, freno.tau), ...
                    'Ku_rpm_s', Ku, 'Ku_rad_s2', Ku * 2 * pi / 60, 'polos_s', polos_s, ...
                    'polos_z', polos_z, 'cero_z', cero_z), ...
      'rampa', rampa, 'validacion_rmse_rpm', mean([validacion.rmse]));
  escribir_json(fullfile(salida, 'modelo.json'), modelo);
  fprintf('Resultados en %s\n', salida);
end

function indice = leer_indice(ruta)
  lineas = strsplit(strtrim(fileread(ruta)), sprintf('\n'));
  campos = strsplit(strtrim(lineas{1}), ',');
  indice = struct();
  for i = 2:numel(lineas)
    valores = strsplit(strtrim(lineas{i}), ',');
    for j = 1:numel(campos)
      indice(i - 1).(campos{j}) = valores{j};
    end
  end
end

function config = leer_config(ruta_csv)
  meta = jsondecode(fileread(strrep(ruta_csv, '.csv', '.json')));
  config = meta.configuracion;
end

function [t, freno, rpm] = leer_ensayo(ruta)
  fid = fopen(ruta, 'r');
  fgetl(fid);
  datos = textscan(fid, '%f %f %f', 'Delimiter', ',', 'TreatAsEmpty', {'nan', '-nan'});
  fclose(fid);
  t = datos{1} / 1000; freno = datos{2}; rpm = datos{3};
end

function [w, a] = pares_indice(carpeta, indice, grupo)
  % Desaceleracion local (recta en ventanas de 0,2 s) contra velocidad, despues del escalon de freno.
  w = []; a = [];
  for i = find(strcmp({indice.grupo}, grupo))
    [t, freno, rpm] = leer_ensayo(fullfile(carpeta, indice(i).archivo));
    desde = t(find(freno ~= freno(1), 1));
    if isempty(desde), desde = 0.1; else, desde = desde + 0.5; end
    for k = find(t >= desde & rpm > 50)'
      cerca = abs(t - t(k)) <= 0.1 & rpm > 50;
      if mod(k, 5) == 0 && sum(cerca) >= 5
        r = polyfit(t(cerca), rpm(cerca), 1);
        w(end + 1, 1) = rpm(k); a(end + 1, 1) = -r(1);
      end
    end
  end
end

function w = respuesta(tt, w0, D, tau, friccion)
  % Solucion exacta de dw/dt = -(c + b w) - D (1 - exp(-t/tau)), w(0) = w0
  c = friccion.c; b = friccion.b; p = 1 / tau;
  A = D / (b - p);
  w = -(c + D) / b + A * exp(-p * tt) + (w0 + (c + D) / b - A) * exp(-b * tt);
end

function [D, tau, rmse, w0] = ajustar_escalon(t, freno, rpm, friccion)
  k = find(freno ~= freno(1), 1);
  tt = t(k:end) - t(k); ww = rpm(k:end);
  usar = ww > 50 & ~isnan(ww);
  w0 = ww(1);
  r = polyfit(tt(usar & tt < 0.5), ww(usar & tt < 0.5), 1);
  inicial = max(10, -r(1) - friccion.c - friccion.b * w0);
  costo = @(x) sum((ww(usar) - respuesta(tt(usar), w0, exp(x(1)), exp(x(2)), friccion)) .^ 2);
  x = fminsearch(costo, [log(inicial), log(0.1)], optimset('Display', 'off', 'MaxFunEvals', 2000));
  D = exp(x(1)); tau = exp(x(2));
  rmse = sqrt(costo(x) / sum(usar));
end

function [tt, medido, modelo_w] = predecir(t, ang, rpm, friccion, freno)
  k = find(ang ~= ang(1), 1);
  tt = t(k:end) - t(k); medido = rpm(k:end);
  D = freno.k * max(0, ang(end) - freno.contacto);
  modelo_w = max(0, respuesta(tt, medido(1), D, freno.tau, friccion));
  parada = find(modelo_w <= 0, 1);
  if ~isempty(parada), modelo_w(parada:end) = 0; end
end

function t_parada = tiempo_parada(tt, w)
  k = find(w <= 0, 1);
  if isempty(k), t_parada = NaN; else, t_parada = tt(k); end
end

function [polos_z, cero_z] = discretizar(Kg, a, p, ts)
  % ZOH de Kg/((s+a)(s+p)): polos exp(-a Ts), exp(-p Ts); un cero real.
  e1 = exp(-a * ts); e2 = exp(-p * ts);
  N = @(z) (z - e1) .* (z - e2) / (a * p) + (z - 1) .* (z - e2) / (a * (a - p)) + (z - 1) .* (z - e1) / (p * (p - a));
  n0 = N(0); n1 = N(1) - n0;
  polos_z = [e1, e2]; cero_z = -n0 / n1;
end

function figura = nueva_figura()
  figura = figure('Visible', 'off', 'Position', [100 100 1100 500]);
end

function guardar_figura(figura, ruta)
  try
    print(figura, ruta, '-dpng', '-r110');
  catch error_figura
    warning('No se pudo guardar %s: %s', ruta, error_figura.message);
  end
  close(figura);
end

function escribir_tabla(ruta, datos)
  fid = fopen(ruta, 'w');
  if isempty(datos), fclose(fid); return; end
  campos = fieldnames(datos);
  fprintf(fid, '%s\n', strjoin(campos', ','));
  for i = 1:numel(datos)
    valores = cellfun(@(c) texto(datos(i).(c)), campos, 'UniformOutput', false);
    fprintf(fid, '%s\n', strjoin(valores', ','));
  end
  fclose(fid);
end

function s = texto(v)
  if ischar(v), s = v; else, s = sprintf('%.6g', v); end
end

function escribir_json(ruta, datos)
  try
    contenido = jsonencode(datos, 'PrettyPrint', true);
  catch
    contenido = jsonencode(datos);
  end
  fid = fopen(ruta, 'w'); fprintf(fid, '%s\n', contenido); fclose(fid);
end
