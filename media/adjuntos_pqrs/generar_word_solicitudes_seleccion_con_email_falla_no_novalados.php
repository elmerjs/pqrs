<?php
require_once 'vendor/autoload.php';
require_once 'conn.php';
require 'funciones.php';

date_default_timezone_set('America/Bogota');

use PhpOffice\PhpWord\SimpleType\Jc;
use PhpOffice\PhpWord\SimpleType\TblWidth;
use PhpOffice\PhpWord\Style\Language;


// ===== INICIA EL NUEVO BLOQUE PARA PHPMailer =====
use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception;

require 'vendor/phpmailer/phpmailer/src/Exception.php';
require 'vendor/phpmailer/phpmailer/src/PHPMailer.php';
require 'vendor/phpmailer/phpmailer/src/SMTP.php';

// Cargar la configuración de correo que ya tienes y funciona
$config = require 'config_email.php';


setlocale(LC_TIME, 'es_ES.UTF-8', 'es_ES', 'Spanish_Spain', 'es');

// --- 1. PARÁMETROS RECIBIDOS ---
$anio_semestre = $_POST['anio_semestre'] ?? '';
$id_facultad = (int)($_POST['id_facultad'] ?? 0);
$numero_oficio = $_POST['oficio'] ?? 'S/N';
$fecha_oficio = $_POST['fecha_oficio'] ?? date('Y-m-d');
$oficio_con_fecha_fac = $numero_oficio . ' ' . $fecha_oficio;

$decano_nombre = $_POST['decano'] ?? 'Decano/a';
$elaborado_por = $_POST['elaborado_por'] ?? 'Responsable Facultad';
$folios = (int)($_POST['folios'] ?? 0);
$numero_acta = $_POST['numero_acta'] ?? '';

$selected_ids_str = $_POST['selected_ids_for_word'] ?? '';
if (empty($selected_ids_str)) {
    die("No se proporcionaron IDs de solicitud válidos.");
}
$selected_ids_array = array_map('intval', explode(',', $selected_ids_str));

if (empty($anio_semestre) || $id_facultad === 0) {
    die("Debe proporcionar el año-semestre y la facultad para generar el oficio.");
}
        $departamento_emails = [];

// ==============================================================================
// ===== INICIO DE LA LÓGICA MEJORADA PARA "CAMBIO DE VINCULACIÓN" ==============
// ==============================================================================

// El array final de IDs que se van a actualizar y a incluir en el Word
$ids_a_procesar = $selected_ids_array;

// Primero, buscamos las cédulas de los registros "Adicionar" que hemos seleccionado
$placeholders = implode(',', array_fill(0, count($selected_ids_array), '?'));
$types = str_repeat('i', count($selected_ids_array));
$sql_find_cedulas = "SELECT cedula FROM solicitudes_working_copy WHERE id_solicitud IN ($placeholders) AND (novedad = 'Adicion' OR novedad = 'adicionar')";

$stmt_cedulas = $conn->prepare($sql_find_cedulas);
if ($stmt_cedulas) {
    $stmt_cedulas->bind_param($types, ...$selected_ids_array);
    $stmt_cedulas->execute();
    $result_cedulas = $stmt_cedulas->get_result();
    $cedulas_de_adiciones = [];
    while ($row = $result_cedulas->fetch_assoc()) {
        $cedulas_de_adiciones[] = $row['cedula'];
    }
    $stmt_cedulas->close();
}

// Si encontramos cédulas, buscamos sus contrapartes "Eliminar" que ya fueron APROBADAS
if (!empty($cedulas_de_adiciones)) {
    $placeholders_cedulas = implode(',', array_fill(0, count($cedulas_de_adiciones), '?'));
    $types_cedulas = str_repeat('s', count($cedulas_de_adiciones));

    $sql_find_eliminar = "SELECT id_solicitud FROM solicitudes_working_copy WHERE cedula IN ($placeholders_cedulas) AND novedad = 'Eliminar' AND anio_semestre = ? AND facultad_id = ? AND estado_facultad = 'APROBADO'";
    $stmt_eliminar = $conn->prepare($sql_find_eliminar);
    
    if ($stmt_eliminar) {
        $params_eliminar = array_merge($cedulas_de_adiciones, [$anio_semestre, $id_facultad]);
        $stmt_eliminar->bind_param($types_cedulas . 'si', ...$params_eliminar);
        
        $stmt_eliminar->execute();
        $result_eliminar = $stmt_eliminar->get_result();
        while ($row = $result_eliminar->fetch_assoc()) {
            // Añadimos el ID del registro "Eliminar" a nuestra lista de procesamiento
            $ids_a_procesar[] = $row['id_solicitud'];
        }
        $stmt_eliminar->close();
    }
}

// Nos aseguramos de que no haya IDs duplicados en la lista final
$ids_a_procesar = array_unique($ids_a_procesar);

// ==============================================================================
// ===== FIN DE LA LÓGICA MEJORADA ==============================================
// ==============================================================================


// === UPDATE PARA CADA SOLICITUD SELECCIONADA (USANDO LA LISTA COMPLETA) ===
$sql_update = "UPDATE solicitudes_working_copy 
               SET oficio_fac = ?, 
                   fecha_oficio_fac = ?, 
                   oficio_con_fecha_fac = ? 
               WHERE id_solicitud = ?";

$stmt_update = $conn->prepare($sql_update);
if (!$stmt_update) {
    die("Error al preparar el UPDATE: " . $conn->error);
}

// Ahora iteramos sobre la lista completa que incluye las contrapartes "Eliminar"
foreach ($ids_a_procesar as $id) {
    $stmt_update->bind_param("sssi", $numero_oficio, $fecha_oficio, $oficio_con_fecha_fac, $id);
    $stmt_update->execute();
}
$stmt_update->close();

// Mapeo de imágenes por facultad
$facultades = [
    1 => ['encab' => 'img/encabezado_decanatura_artes.png', 'pie' => 'img/pieartes.png'],
    2 => ['encab' => 'img/encabezado_decanatura_agrarias.png', 'pie' => 'img/pieagro.png'],
    3 => ['encab' => 'img/encabezado_decanatura_salud.png', 'pie' => 'img/piesalud.png'],
    4 => ['encab' => 'img/encabezado_decanatura_fccea.png', 'pie' => 'img/piecontables.png'],
    5 => ['encab' => 'img/encabezado_decanatura_humanas.png', 'pie' => 'img/piehumanas.png'],
    6 => ['encab' => 'img/encabezado_decanatura_facnedx.png', 'pie' => 'img/piefacned.png'],
    7 => ['encab' => 'img/encabezado_decanatura_derecho.png', 'pie' => 'img/piederecho.png'],
    8 => ['encab' => 'img/encabezado_decanatura_civil.png', 'pie' => 'img/piecivil.png'],
    9 => ['encab' => 'img/encabezado_decanatura_fiet.png', 'pie' => 'img/piefiet.png']
];

// Determinar imágenes según facultad
if (isset($facultades[$id_facultad])) {
    $imgencabezado = $facultades[$id_facultad]['encab'];
    $imgpie = $facultades[$id_facultad]['pie'];
} else {
    $imgencabezado = 'img/encabezado_generico.png';
    $imgpie = 'img/piegenerico.png';
}

// Función auxiliar para bind_param, necesaria cuando se usa call_user_func_array
function refValues($arr){
    if (strnatcmp(phpversion(),'5.3') >= 0) //PHP 5.3+
    {
        $refs = array();
        foreach($arr as $key => $value)
            $refs[$key] = &$arr[$key];
        return $refs;
    }
    return $arr;
}

// ===================================================================
// LÓGICA PARA DETECTAR Y PROCESAR "CAMBIO DE VINCULACIÓN"
// ===================================================================
$cambio_vinculacion_data = [];
$cedulas_cambio_vinculacion = [];
$ids_cambio_vinculacion = []; // IDs de las solicitudes que son "Cambio de Vinculación"

// Primero, identificar los pares de "eliminar" y "adicionar" dentro de los IDs seleccionados
$placeholders_ids_seleccionados = implode(',', array_fill(0, count($selected_ids_array), '?'));

$sql_cambio_vinculacion = "
    SELECT
        t1.id_solicitud AS id_eliminar,
        t1.cedula,
        t1.departamento_id,
        t1.nombre AS nombre_eliminar,
        t1.tipo_dedicacion AS dedicacion_eliminar,
        t1.tipo_dedicacion_r AS dedicacion_eliminar_r,

        t1.horas AS horas_eliminar,
        t1.horas_r AS horas_r_eliminar,

        t1.s_observacion AS observacion_eliminar,
        t2.id_solicitud AS id_adicionar,
        t2.nombre AS nombre_adicionar,
        t1.tipo_docente as tipo_docente_eliminar,
        t2.tipo_docente,
        t2.tipo_dedicacion AS dedicacion_adicionar,
        t2.horas AS horas_adicionar,
        t2.tipo_dedicacion_r,
        t2.horas_r,
        t1.sede as sede_eliminar,
        t2.sede as sede_adicionar,
        t2.s_observacion AS observacion_adicionar,
        t2.anexa_hv_docente_nuevo,
        t2.actualiza_hv_antiguo,
        f.nombre_fac_minb AS nombre_facultad,
        d.depto_nom_propio AS nombre_departamento
    FROM solicitudes_working_copy t1
    JOIN solicitudes_working_copy t2
        ON t1.cedula = t2.cedula
        AND t1.departamento_id = t2.departamento_id
        AND t1.anio_semestre = t2.anio_semestre
    JOIN facultad f ON t1.facultad_id = f.PK_FAC
    JOIN deparmanentos d ON t1.departamento_id = d.PK_DEPTO
    WHERE t1.novedad = 'eliminar'
      AND t2.novedad = 'adicionar'
      AND t1.anio_semestre = ?
      AND t1.facultad_id = ?
      AND t1.estado_facultad = 'APROBADO'
      AND t1.estado_vra = 'PENDIENTE'
      AND t2.estado_facultad = 'APROBADO'
      AND t2.estado_vra = 'PENDIENTE'
      AND t1.id_solicitud IN ($placeholders_ids_seleccionados)
      AND t2.id_solicitud IN ($placeholders_ids_seleccionados)
    ORDER BY d.depto_nom_propio ASC, t1.nombre ASC
";

$stmt_cambio_vinculacion = $conn->prepare($sql_cambio_vinculacion);
if ($stmt_cambio_vinculacion) {
    $types_cambio = 'si' . str_repeat('i', count($selected_ids_array) * 2);
    $params_cambio = array_merge([$types_cambio, $anio_semestre, $id_facultad], $selected_ids_array, $selected_ids_array);
    call_user_func_array([$stmt_cambio_vinculacion, 'bind_param'], refValues($params_cambio));
    
    if (!$stmt_cambio_vinculacion->execute()) {
        die("Error al ejecutar la consulta de cambio de vinculación: " . $stmt_cambio_vinculacion->error);
    }
    
    $result_cambio_vinculacion = $stmt_cambio_vinculacion->get_result();
    while ($row = $result_cambio_vinculacion->fetch_assoc()) {
        $cambio_vinculacion_data[] = $row;
        $cedulas_cambio_vinculacion[] = $row['cedula'];
        $ids_cambio_vinculacion[] = $row['id_eliminar'];
        $ids_cambio_vinculacion[] = $row['id_adicionar'];
    }
    $stmt_cambio_vinculacion->close();
} else {
    die("Error al preparar la consulta de cambio de vinculación: " . $conn->error);
}

// Convertir las cédulas de cambio de vinculación y los IDs a un string para la cláusula IN
// Solo únicos para evitar problemas con la cláusula IN
$cedulas_excluir = array_unique($cedulas_cambio_vinculacion);
$cedulas_excluir_str = !empty($cedulas_excluir) ? "'" . implode("','", $cedulas_excluir) . "'" : "'_NONE_'"; // Usa un valor que no exista si el array está vacío

$ids_excluir = array_unique($ids_cambio_vinculacion);
$ids_excluir_str = !empty($ids_excluir) ? implode(',', $ids_excluir) : '0'; // Usa 0 si el array está vacío

// === MODIFICACIÓN DE LA CONSULTA SQL PRINCIPAL PARA EXCLUIR CAMBIOS DE VINCULACIÓN ===
$sql = "
    SELECT
        sw.id_solicitud,
        sw.cedula,
        sw.nombre,
        sw.novedad,
        sw.tipo_docente,
        sw.tipo_dedicacion,
        sw.horas,
        sw.tipo_dedicacion_r,
        sw.horas_r,
        sw.s_observacion,
        sw.observacion_facultad,
        sw.costo,
        sw.anexa_hv_docente_nuevo,
        sw.actualiza_hv_antiguo,
        f.nombre_fac_minb AS nombre_facultad,
        d.depto_nom_propio AS nombre_departamento
    FROM solicitudes_working_copy sw
    JOIN facultad f ON sw.facultad_id = f.PK_FAC
    JOIN deparmanentos d ON sw.departamento_id = d.PK_DEPTO
    WHERE sw.anio_semestre = ?
      AND sw.facultad_id = ?
      AND sw.estado_facultad = 'APROBADO'
      AND sw.estado_vra = 'PENDIENTE'
      AND sw.id_solicitud IN ($placeholders_ids_seleccionados)
";

// Si hay IDs para excluir (cambios de vinculación), añadimos la cláusula NOT IN
if (!empty($ids_excluir)) {
    $placeholders_excluir = implode(',', array_fill(0, count($ids_excluir), '?'));
    $sql .= " AND sw.id_solicitud NOT IN ($placeholders_excluir)";
}

$sql .= " ORDER BY d.depto_nom_propio ASC, sw.novedad ASC, sw.nombre ASC";

$stmt = $conn->prepare($sql);
if ($stmt) {
    // Construir los tipos y parámetros para bind_param
    $types = 'si' . str_repeat('i', count($selected_ids_array));
    $params = array_merge([$anio_semestre, $id_facultad], $selected_ids_array);

    // Si hay IDs para excluir, añadimos sus tipos y parámetros
    if (!empty($ids_excluir)) {
        $types .= str_repeat('i', count($ids_excluir));
        $params = array_merge($params, $ids_excluir);
    }

    // Usar call_user_func_array para bind_param
    call_user_func_array([$stmt, 'bind_param'], refValues(array_merge([$types], $params)));

    $stmt->execute();
    $result = $stmt->get_result();
    $solicitudes = $result->fetch_all(MYSQLI_ASSOC);
    $stmt->close();
} else {
    die("Error al preparar la consulta de solicitudes: " . $conn->error);
}

if (empty($solicitudes) && empty($cambio_vinculacion_data)) {
    die("No se encontraron solicitudes APROBADAS por Facultad y PENDIENTES por VRA para el periodo, facultad y IDs seleccionados.");
}

// ==============================================================================
// ===== INICIA EL BLOQUE DE CÓDIGO CORREGIDO ===================================
// ==============================================================================

// --- OBTENER NOMBRES PARA EL ENCABEZADO DEL DOCUMENTO ---
$nombre_facultad_principal = ($solicitudes[0]['nombre_facultad'] ?? $cambio_vinculacion_data[0]['nombre_facultad']) ?? 'Facultad Desconocida';

// Obtener nombres de los departamentos involucrados directamente de los datos que ya tenemos
$departamentos_nombres = [];
$todos_los_datos = array_merge($solicitudes, $cambio_vinculacion_data);
foreach ($todos_los_datos as $dato) {
    if (!in_array($dato['nombre_departamento'], $departamentos_nombres)) {
        $departamentos_nombres[] = htmlspecialchars($dato['nombre_departamento']);
    }
}
$departamentos_nombres = array_unique($departamentos_nombres);

$departamentos_frase = '';
if (!empty($departamentos_nombres)) {
    $num_deptos = count($departamentos_nombres);
    if ($num_deptos === 1) {
        $departamentos_frase = $departamentos_nombres[0];
    } elseif ($num_deptos > 1) {
        $ultimo_depto = array_pop($departamentos_nombres);
        $departamentos_frase = implode(', ', $departamentos_nombres) . ' y ' . $ultimo_depto;
    }
}

// --- AGRUPAR LAS SOLICITUDES POR TIPO Y DEPARTAMENTO ---
$grouped_solicitudes = []; // Para Adicionar, Eliminar, etc.
foreach ($solicitudes as $sol) {
    $grouped_solicitudes[$sol['nombre_departamento']][$sol['novedad']][] = $sol;
}

$grouped_cambio_vinculacion = []; // Exclusivamente para Cambios de Vinculación
foreach ($cambio_vinculacion_data as $cambio) {
    $grouped_cambio_vinculacion[$cambio['nombre_departamento']][] = $cambio;
}

// Generar el documento de Word usando PHPWord
$phpWord = new \PhpOffice\PhpWord\PhpWord();
// Configurar idioma español (Colombia)
$phpWord->getSettings()->setThemeFontLang(new Language(Language::ES_ES));

// Estilos
$phpWord->addFontStyle('boldSize12', ['bold' => true, 'size' => 12]);
$phpWord->addFontStyle('normalSize11', ['size' => 11]);
$phpWord->addFontStyle('normalSize9', ['size' => 9]);
$phpWord->addParagraphStyle('center', ['alignment' => Jc::CENTER]);
$phpWord->addParagraphStyle('justify', ['alignment' => Jc::BOTH]);
$phpWord->addParagraphStyle('left', ['alignment' => Jc::LEFT]);

// Estilos para tabla
$styleTable = array(
    'borderSize' => 6,
    'borderColor' => '999999',
    'cellMargin' => 60,
    'alignment' => Jc::CENTER
);
$phpWord->addTableStyle('ColspanRowspan', $styleTable);

$cellTextStyle = ['size' => 9, 'bold' => false];
$cellTextStyleb = ['size' => 9, 'bold' => true];
$paragraphStyle = ['alignment' => Jc::CENTER, 'spaceAfter' => 0];
$headerCellStyle = [
    'bgColor' => 'F2F2F2',
    'borderSize' => 6,
    'borderColor' => '999999',
    'valign' => 'center'
];

$fontStyleb = ['bold' => true, 'size' => 10];
$observationTextStyle = ['size' => 11];
$paragraphStyleLeft = ['alignment' => Jc::LEFT];

// ==================================================
// SECCIÓN CON MÁRGENES PARA ENCABEZADO/PIE
// ==================================================
$section = $phpWord->addSection([
    'marginTop'    => 1200,  // Espacio para encabezado (1200 twips = ~2.12 cm)
    'marginBottom' => 1000,  // Espacio para pie de página
    'marginLeft'   => 1000,
    'marginRight'  => 1000
]);

// ==================================================
// ENCABEZADO CON IMAGEN
// ==================================================
$header = $section->addHeader();
$header->addImage($imgencabezado, [
    'width'       => 200,
    'alignment'   => Jc::LEFT
]);

// ==================================================
// PIE DE PÁGINA CON IMAGEN
// ==================================================
$footer = $section->addFooter();
$footer->addImage($imgpie, [
    'width'       => 450,
    'alignment'   => Jc::CENTER
]);

// ==================================================
// CONTENIDO DEL DOCUMENTO
// ==================================================
$section->addTextBreak(0);  // Espacio después del encabezado
$paragraphStylexz = array('lineHeight' => 0.8, 'spaceAfter' => 0, 'spaceBefore' => 0);
$styleNoSpace = ['align' => 'left', 'spaceAfter' => 0];

$fontStylecuerpo = array('name' => 'Arial', 'size' => 11);
$fecha_actual = strftime('%d de %B de %Y', strtotime($fecha_oficio));

$section->addText($numero_oficio, ['size' => 11], $styleNoSpace);
$section->addText('Popayán, ' . $fecha_actual,$fontStylecuerpo,$paragraphStylexz);
if (!empty($numero_acta)) {
    $section->addText('Número de Acta: ' . $numero_acta, 'normalSize11', 'center');
}
$section->addTextBreak(1);

// Destinatario (Vicerrectoría Académica)
// Obtener datos del vicerrector
$vicerrector = formatearVicerrectorParaOficio();

// Destinatario (Vicerrectoría Académica)
$section->addText($vicerrector['titulo'], ['size' => 11], $styleNoSpace);
$section->addText($vicerrector['nombre'], ['size' => 11], $styleNoSpace);
$section->addText($vicerrector['cargo_completo'], ['size' => 11], $styleNoSpace);
$section->addText($vicerrector['institucion'], ['size' => 11], $styleNoSpace);
$section->addTextBreak(1);


$section->addText(
    'Asunto: Novedades de Vinculación Profesores temporales ' . $anio_semestre . '.',
    [ 'size' => 11], 'left'
);
$section->addTextBreak(1);

$section->addText('Cordial saludo,', 'normalSize11', 'left');
$section->addTextBreak(0);

$section->addText(
    'Para su conocimiento y trámite pertinente remito solicitud de novedades de la Facultad de ' . $nombre_facultad_principal . /*' departamento: '.$departamentos_frase . */'; periodo: ' . $anio_semestre . ',  para los siguientes profesores:',
    'normalSize11', 'justify'
);
$section->addTextBreak(1);

// --- BUCLE PRINCIPAL POR DEPARTAMENTO ---
$todos_los_departamentos = array_unique(array_merge(array_keys($grouped_solicitudes), array_keys($grouped_cambio_vinculacion)));
sort($todos_los_departamentos);

foreach ($todos_los_departamentos as $departamento_nombre) {
    // Título del Departamento
    $section->addText('Departamento de ' . htmlspecialchars($departamento_nombre), ['bold' => true, 'size' => 12], ['spaceAfter' => 120, 'keepNext' => true]);

    // --- SECCIÓN 1: CAMBIOS DE VINCULACIÓN (si existen para este depto) ---
    if (isset($grouped_cambio_vinculacion[$departamento_nombre])) {
        $section->addText('Novedad: Cambio de Vinculación', ['bold' => true, 'size' => 11]);
        $section->addTextBreak(0);

        foreach ($grouped_cambio_vinculacion[$departamento_nombre] as $cambio) {
            // 1. Añadir la observación general/contexto al inicio (si existe)
            if (!empty($cambio['observacion_adicionar'])) {
                $section->addText(htmlspecialchars($cambio['observacion_adicionar']), $observationTextStyle, $paragraphStyleLeft);
            }

            // 2. Construir la frase narrativa de transición del profesor
            $tipo_docente_eliminar = $cambio['tipo_docente_eliminar'];
            $salida_part = ''; // Inicializar para la parte de la salida
            $sede_eliminar = htmlspecialchars($cambio['sede_eliminar'] ?: ''); // Obtener el valor de la sede a eliminar aquí
            
            // Determinar los valores para la vinculación que se elimina
            if ($tipo_docente_eliminar == "Ocasional") {
                // Para Ocasional, usar dedicación (MT o TC) - priorizar el campo principal, sino el _r
                $dedicacion_eliminar_val = !empty($cambio['dedicacion_eliminar']) ? $cambio['dedicacion_eliminar'] : $cambio['dedicacion_eliminar_r'];
                $dedicacion_eliminar_str = '';
                
                if (!empty($dedicacion_eliminar_val)) {
                    // Convertir abreviaciones a texto completo
                    $dedicacion_eliminar_str = str_replace(
                        ['MT', 'TC'], 
                        ['Medio Tiempo', 'Tiempo Completo'], 
                        htmlspecialchars($dedicacion_eliminar_val)
                    );
                     // MODIFICACIÓN AQUÍ para Ocasional Eliminación: Añadir la sede si existe
                    if (!empty($sede_eliminar)) {
                        $dedicacion_eliminar_str .= " - Sede {$sede_eliminar}";
                    }
                }
                
                $salida_part = $dedicacion_eliminar_str;
            } else if ($tipo_docente_eliminar == "Catedra") {
            $horas_eliminar_p_val = null; // Usaremos null para saber si el valor es válido y > 0
            $horas_eliminar_r_val = null;

            // Evaluar horas_eliminar (propuesta)
            if (isset($cambio['horas_eliminar']) && is_numeric($cambio['horas_eliminar'])) {
                $temp_p = floatval($cambio['horas_eliminar']);
                if ($temp_p > 0) {
                    $horas_eliminar_p_val = htmlspecialchars((string)$temp_p);
                }
            }

            // Evaluar horas_r_eliminar (regular/regional)
            // Asumiendo que 'horas_r_eliminar' es el campo correcto para las horas regulares a eliminar
            if (isset($cambio['horas_r_eliminar']) && is_numeric($cambio['horas_r_eliminar'])) {
                $temp_r = floatval($cambio['horas_r_eliminar']);
                if ($temp_r > 0) {
                    $horas_eliminar_r_val = htmlspecialchars((string)$temp_r);
                }
            }
            
            $horas_eliminar_str = '';
            if ($horas_eliminar_p_val !== null && $horas_eliminar_r_val !== null) {
                // Ambas tienen valores válidos y > 0
                $horas_eliminar_str = "{$horas_eliminar_p_val} (P) / {$horas_eliminar_r_val} (R) horas";
            } elseif ($horas_eliminar_p_val !== null) {
                // Solo horas_eliminar tiene un valor válido y > 0
                $horas_eliminar_str = "{$horas_eliminar_p_val} horas";
            } elseif ($horas_eliminar_r_val !== null) {
                // Solo horas_r_eliminar tiene un valor válido y > 0
                $horas_eliminar_str = "{$horas_eliminar_r_val} horas";
            }
            
            $salida_part = $horas_eliminar_str;
            
            // Concatenar la sede si existe y hay alguna hora válida para mostrar
            if (!empty($sede_eliminar) && !empty($salida_part)) { // Se agregó !empty($salida_part) para que la sede solo se añada si hay horas
                $salida_part .= " - Sede {$sede_eliminar}";
            }
        } else {
                $salida_part = '';
            }
            $sede_adicionar = htmlspecialchars($cambio['sede_adicionar'] ?: ''); // Obtener el valor de la sede aquí

            // --- Lógica para determinar los valores de la NUEVA vinculación (adicionar) ---
            $tipo_docente_str = htmlspecialchars($cambio['tipo_docente'] ?: '');
            $nueva_vinculacion_dedicacion_horas = '';

            if ($tipo_docente_str === "Ocasional") {
                $dedicacion_val_adicionar = '';
                if (!empty($cambio['dedicacion_adicionar'])) {
                    $dedicacion_val_adicionar = $cambio['dedicacion_adicionar'];
                } elseif (!empty($cambio['tipo_dedicacion_r'])) {
                    $dedicacion_val_adicionar = $cambio['tipo_dedicacion_r'];
                }

                if (!empty($dedicacion_val_adicionar)) {
                    $nueva_vinculacion_dedicacion_horas = str_replace(
                        ['MT', 'TC'],
                        ['Medio Tiempo', 'Tiempo Completo'],
                        htmlspecialchars($dedicacion_val_adicionar)
                    );
                     // **MODIFICACIÓN AQUÍ para Ocasional:** Añadir la sede si existe
                    if (!empty($sede_adicionar)) {
                        $nueva_vinculacion_dedicacion_horas .= " - Sede {$sede_adicionar}";
                    }
                }
            } elseif ($tipo_docente_str === "Catedra") {
                $horas_val_adicionar_numeric = null; // Almacenará el valor numérico válido y > 0

                // Evaluar horas_adicionar
                if (isset($cambio['horas_adicionar']) && is_numeric($cambio['horas_adicionar'])) {
                    $temp_horas_adicionar = floatval($cambio['horas_adicionar']);
                    if ($temp_horas_adicionar > 0) {
                        $horas_val_adicionar_numeric = $temp_horas_adicionar;
                    }
                }

                // Si horas_adicionar no es válido o es 0, evaluar horas_r
                if ($horas_val_adicionar_numeric === null && isset($cambio['horas_r']) && is_numeric($cambio['horas_r'])) {
                    $temp_horas_r = floatval($cambio['horas_r']);
                    if ($temp_horas_r > 0) {
                        $horas_val_adicionar_numeric = $temp_horas_r;
                    }
                }

                if ($horas_val_adicionar_numeric !== null) {
                    $nueva_vinculacion_dedicacion_horas = htmlspecialchars((string)$horas_val_adicionar_numeric) . ' horas';
                    // **MODIFICACIÓN AQUÍ para Catedra:** Añadir la sede si existe
                    if (!empty($sede_adicionar)) {
                        $nueva_vinculacion_dedicacion_horas .= " - Sede {$sede_adicionar}";
                    }
                }
            }
            // Fin de la lógica para ADICIONAR
            $nombre_profesor = htmlspecialchars($cambio['nombre_adicionar'] ?: $cambio['nombre_eliminar']);
        $section->addTextBreak(0);

            // Construcción del texto narrativo con lógica mejorada
            $narrative_text = /*"Con el fin de atender esta necesidad, solicitamos comedidamente  */ "El(la) profesor(a) {$nombre_profesor}";
            
            // Parte de la vinculación actual (que se elimina)
            $narrative_text .= "  pasa de {$tipo_docente_eliminar}";
            if (!empty($salida_part)) {
                $narrative_text .= " - {$salida_part}";
            }
            
            // Parte de la nueva vinculación
            $narrative_text .= " a {$tipo_docente_str}";
            if (!empty($nueva_vinculacion_dedicacion_horas)) {
                $narrative_text .= " {$nueva_vinculacion_dedicacion_horas}";
            }
            $narrative_text .= ".";

            $section->addText($narrative_text, ['size' => 11], $paragraphStyleLeft);
            $section->addTextBreak(0); // Pequeña separación

            // 3. Tabla para la "Nueva Vinculación"
           $section->addText('Nueva Vinculación:', ['bold' => true, 'size' => 9], $paragraphStyleLeft);
            $table_cambio = $section->addTable('ColspanRowspan');
            $table_cambio->setWidth(100 * 50, TblWidth::PERCENT);

            // Encabezados de tabla - Primera fila (para las celdas que abarcan dos filas)
            $row = $table_cambio->addRow();

            // Cédula
            $row->addCell(1200, array_merge($headerCellStyle, array('vMerge' => 'restart')))->addText('Cédula', $cellTextStyleb, $paragraphStyle);

            // Nombre
            $row->addCell(4000, array_merge($headerCellStyle, array('vMerge' => 'restart')))->addText('Nombre', $cellTextStyleb, $paragraphStyle);

            // Dedicación/hr (cabecera que abarca two columns)
            $row->addCell(2600, array_merge($headerCellStyle, array('alignment' => Jc::CENTER, 'gridSpan' => 2, 'vMerge' => 'restart')))->addText('Dedic/hr', $cellTextStyleb, $paragraphStyle);
            
            // Hoja de vida (cabecera que abarca two columns)
            $row->addCell(2000, array_merge($headerCellStyle, array('alignment' => Jc::CENTER, 'gridSpan' => 2, 'vMerge' => 'restart')))->addText('H.de Vida', $cellTextStyleb, $paragraphStyle);

            // Tipo Docente (última columna)
            $row->addCell(1000, array_merge($headerCellStyle, array('vMerge' => 'restart')))->addText('Tipo Docente', $cellTextStyleb, $paragraphStyle);

            // Encabezados de tabla - Segunda fila (para sub-encabezados y 'continue' de vMerge)
            $row = $table_cambio->addRow();

            // Celdas 'continue' para Cédula y Nombre (y Nº si la tuvieras)
            $row->addCell(1200, array('vMerge' => 'continue', 'borderSize' => 1)); // Cédula
            $row->addCell(4000, array('vMerge' => 'continue', 'borderSize' => 1)); // Nombre

            // Sub-encabezados de Dedicación/hr
            $row->addCell(1300, $headerCellStyle)->addText('Pop', $cellTextStyleb, $paragraphStyle);
            $row->addCell(1300, $headerCellStyle)->addText('Reg', $cellTextStyleb, $paragraphStyle);

            // Sub-encabezados de Hoja de vida
            $row->addCell(1000, $headerCellStyle)->addText('Nuevo', $cellTextStyleb, $paragraphStyle);
            $row->addCell(1000, $headerCellStyle)->addText('Antig', $cellTextStyleb, $paragraphStyle);

            // Celda 'continue' para Tipo Docente
            $row->addCell(1000, array('vMerge' => 'continue', 'borderSize' => 1)); // Tipo Docente

            // Fila de datos
            $table_cambio->addRow();
            // Datos de las nuevas columnas
            $table_cambio->addCell(1200, ['borderSize' => 1, 'valign' => 'center'])->addText(htmlspecialchars($cambio['cedula'] ?: ''), $cellTextStyle, $paragraphStyle);
            $table_cambio->addCell(4000, ['borderSize' => 1, 'valign' => 'center'])->addText(htmlspecialchars($cambio['nombre_adicionar'] ?: ''), $cellTextStyle, $paragraphStyle);
            
            // Columnas de Dedicación/horas según el tipo de docente
            if ($cambio['tipo_docente'] == "Ocasional") {
                $table_cambio->addCell(1300, ['borderSize' => 1, 'valign' => 'center'])->addText(htmlspecialchars($cambio['dedicacion_adicionar'] ?: ''), $cellTextStyle, $paragraphStyle);
                $table_cambio->addCell(1300, ['borderSize' => 1, 'valign' => 'center'])->addText(htmlspecialchars($cambio['tipo_dedicacion_r'] ?: ''), $cellTextStyle, $paragraphStyle);
            } elseif ($cambio['tipo_docente'] == "Catedra") {
                $table_cambio->addCell(1300, ['borderSize' => 1, 'valign' => 'center'])->addText(htmlspecialchars($cambio['horas_adicionar'] ?: ''), $cellTextStyle, $paragraphStyle);
                $table_cambio->addCell(1300, ['borderSize' => 1, 'valign' => 'center'])->addText(htmlspecialchars($cambio['horas_r'] ?: ''), $cellTextStyle, $paragraphStyle);
            } else {
                $table_cambio->addCell(1300, ['borderSize' => 1, 'valign' => 'center'])->addText('', $cellTextStyle, $paragraphStyle);
                $table_cambio->addCell(1300, ['borderSize' => 1, 'valign' => 'center'])->addText('', $cellTextStyle, $paragraphStyle);
            }

            // Columnas de Hoja de Vida
            $table_cambio->addCell(1000, ['borderSize' => 1, 'valign' => 'center'])
                ->addText(mb_strtoupper(htmlspecialchars($cambio['anexa_hv_docente_nuevo'] ?: ''), 'UTF-8'), $cellTextStyle, $paragraphStyle);
            $table_cambio->addCell(1000, ['borderSize' => 1, 'valign' => 'center'])
                ->addText(mb_strtoupper(htmlspecialchars($cambio['actualiza_hv_antiguo'] ?: ''), 'UTF-8'), $cellTextStyle, $paragraphStyle);

            // Columna Tipo Docente
            $table_cambio->addCell(1000, ['borderSize' => 1, 'valign' => 'center'])->addText(htmlspecialchars($cambio['tipo_docente'] ?: ''), $cellTextStyle, $paragraphStyle);
            
            $section->addTextBreak(1); // Un salto de línea después de cada cambio de vinculación
        }
        // La línea siguiente estaba fuera del foreach, se mantiene así si es tu intención
        $section->addTextBreak(1);
    }

    // --- SECCIÓN 2: NOVEDADES REGULARES (si existen para este depto) ---
    if (isset($grouped_solicitudes[$departamento_nombre])) {
        foreach ($grouped_solicitudes[$departamento_nombre] as $novedad_tipo => $solicitudes_por_novedad) {
            $novedad_mostrar = ucfirst($novedad_tipo);
            $section->addText('Novedad: ' . htmlspecialchars($novedad_mostrar), $fontStyleb, $paragraphStyleLeft);

            // Observaciones (si las hay)
            $observations = [];
            foreach ($solicitudes_por_novedad as $sol) {
                if (!empty($sol['s_observacion']) && !in_array($sol['s_observacion'], $observations)) {
                    $observations[] = $sol['s_observacion'];
                }
            }
            if (!empty($observations)) {
                $observation_text = '';
                foreach ($observations as $index => $obs) {
                    $observation_text .= '(' . ($index + 1) . ') ' . htmlspecialchars($obs) . ' ';
                }
                $section->addText($observation_text, $observationTextStyle, $paragraphStyleLeft);
                $section->addTextBreak(0);
            }
            $section->addTextBreak(0);

            $table = $section->addTable('ColspanRowspan');
            $table->setWidth(100 * 50, TblWidth::PERCENT);

            // Encabezados de la tabla - Primera fila
            $row = $table->addRow();

            // Nº
            $textrun = $row->addCell(400, array_merge($headerCellStyle, array('vMerge' => 'restart')))->addTextRun($paragraphStyle);
            $textrun->addText('N', $cellTextStyle);
            $textrun->addText('o', array_merge($cellTextStyle, array('superScript' => true)));

            // Cédula
            $row->addCell(1200, array_merge($headerCellStyle, array('vMerge' => 'restart')))->addText('Cédula', $cellTextStyle, $paragraphStyle);

            // Nombre
            $row->addCell(4000, array_merge($headerCellStyle, array('vMerge' => 'restart')))->addText('Nombre', $cellTextStyle, $paragraphStyle);

            // Dedicación/hr
            $row->addCell(1400, array_merge($headerCellStyle, array('alignment' => Jc::CENTER, 'gridSpan' => 2, 'vMerge' => 'restart')))->addText('Dedic/hr', $cellTextStyle, $paragraphStyle);

            // Hoja de vida
            $row->addCell(700, array_merge($headerCellStyle, array('alignment' => Jc::CENTER, 'gridSpan' => 2, 'vMerge' => 'restart')))->addText('H.de Vida', $cellTextStyle, $paragraphStyle);

            // Tipo Docente
            $row->addCell(1000, array_merge($headerCellStyle, array('vMerge' => 'restart')))->addText('Tipo Docente', $cellTextStyle, $paragraphStyle);


            // Encabezados de la tabla - Segunda fila
            $row = $table->addRow();
            // Celdas 'continue' para los vMerge 'restart' de la fila anterior
            $row->addCell(400, array('vMerge' => 'continue', 'borderSize' => 6, 'borderColor' => '999999')); // Nº
            $row->addCell(1200, array('vMerge' => 'continue', 'borderSize' => 6, 'borderColor' => '999999')); // Cédula
            $row->addCell(4000, array('vMerge' => 'continue', 'borderSize' => 6, 'borderColor' => '999999')); // Nombre

            // Sub-encabezados de Dedicación/hr
            $row->addCell(700, $headerCellStyle)->addText('Pop', $cellTextStyleb, $paragraphStyle);
            $row->addCell(700, $headerCellStyle)->addText('Reg', $cellTextStyleb, $paragraphStyle);

            // Sub-encabezados de Hoja de vida
            $row->addCell(350, $headerCellStyle)->addText('Nuevo', $cellTextStyleb, $paragraphStyle);
            $row->addCell(350, $headerCellStyle)->addText('Antig', $cellTextStyleb, $paragraphStyle);

            // Celdas 'continue' para Tipo Docente
            $row->addCell(1000, array('vMerge' => 'continue', 'borderSize' => 6, 'borderColor' => '999999')); // Tipo Docente

            $cont = 0; // Contador de filas dentro de cada tabla de novedad
            foreach ($solicitudes_por_novedad as $sol) {
                $cont++;
                $table->addRow();

                // Columna Nº
                $table->addCell(400, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])->addText($cont, $cellTextStyle, $paragraphStyle);

                // Columna Cédula
                $table->addCell(1200, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])->addText(htmlspecialchars($sol['cedula'] ?: ''), $cellTextStyle, $paragraphStyle);

                // Columna Nombre
                $full_nombre = htmlspecialchars($sol['nombre'] ?: '');
                $table->addCell(4000, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])->addText($full_nombre, $cellTextStyle, $paragraphStyle);

                // Columnas de Dedicación/horas según el tipo de docente
                if ($sol['tipo_docente'] == "Ocasional") {
                    $table->addCell(700, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])->addText(htmlspecialchars($sol['tipo_dedicacion'] ?: ''), $cellTextStyle, $paragraphStyle);
                    $table->addCell(700, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])->addText(htmlspecialchars($sol['tipo_dedicacion_r'] ?: ''), $cellTextStyle, $paragraphStyle);
                } elseif ($sol['tipo_docente'] == "Catedra") {
                    $table->addCell(700, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])->addText(htmlspecialchars($sol['horas'] ?: ''), $cellTextStyle, $paragraphStyle);
                    $table->addCell(700, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])->addText(htmlspecialchars($sol['horas_r'] ?: ''), $cellTextStyle, $paragraphStyle);
                } else {
                    $table->addCell(700, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])->addText('', $cellTextStyle, $paragraphStyle);
                    $table->addCell(700, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])->addText('', $cellTextStyle, $paragraphStyle);
                }

                // Columnas de Hoja de Vida
                $table->addCell(350, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])
                    ->addText(mb_strtoupper(htmlspecialchars($sol['anexa_hv_docente_nuevo'] ?: ''), 'UTF-8'), $cellTextStyle, $paragraphStyle);

                $table->addCell(350, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])
                    ->addText(mb_strtoupper(htmlspecialchars($sol['actualiza_hv_antiguo'] ?: ''), 'UTF-8'), $cellTextStyle, $paragraphStyle);

                // Columna Tipo Docente
                $table->addCell(1000, ['borderSize' => 1, 'marginTop' => 0, 'marginBottom' => 0])
                    ->addText(htmlspecialchars($sol['tipo_docente'] ?: ''), $cellTextStyle, $paragraphStyle);
            }
            $section->addTextBreak(1); // Espacio entre tablas de novedad
        }
    }
}

$section->addTextBreak(1);
/*$section->addText(
    'Agradezco su atención al presente. Para cualquier inquietud, no dude en contactarme.',
    'normalSize11', 'justify'
);*/
//$section->addTextBreak(1);

// Firma (Decano)
$section->addText(
    'Universitariamente,',
    'normalSize11', 'left'
);
$section->addTextBreak(2);

$section->addText(
    $decano_nombre,
    ['bold' => true, 'size' => 11], 'left'
);
$section->addText(
    'Decano/a de la Facultad de ' . $nombre_facultad_principal,
    'normalSize11', 'left'
);
$section->addTextBreak(1);
$section->addText(
    'Elaborado por: ' . $elaborado_por,
    'normalSize9', 'left'
);
$section->addText(
    'Folios: ' . $folios,
    'normalSize9', 'left'
);
// ===== INICIA EL NUEVO BLOQUE DE ENVÍO DE CORREO (CORREGIDO) =====

// 1. Agrupamos todas las solicitudes por departamento para enviar un correo consolidado a cada uno.
//    Reutilizamos la variable '$grouped_solicitudes' que ya contiene toda la información.
$emails_a_enviar = [];
foreach ($grouped_solicitudes as $nombre_depto => $novedades_del_depto) {
    foreach ($novedades_del_depto as $tipo_novedad => $solicitudes) {
        foreach ($solicitudes as $sol) {
            $email_depto_mail = 'elmerjs@unicauca.edu.co'; // Para pruebas
            // $email_depto_mail = $sol['email_depto']; // Línea para producción

            if (!empty($email_depto_mail)) {
                // Inicializamos el array para este departamento si es la primera vez que lo vemos.
                if (!isset($emails_a_enviar[$email_depto_mail])) {
                    $emails_a_enviar[$email_depto_mail] = [
                        'nombre_depto' => $nombre_depto, // Usamos el nombre del depto del bucle principal
                        'solicitudes' => []
                    ];
                }
                // Añadimos la solicitud actual al grupo de su departamento.
                $emails_a_enviar[$email_depto_mail]['solicitudes'][] = $sol;
            }
        }
    }
}

// 2. Ahora, recorremos los departamentos agrupados y enviamos un correo a cada uno.
$email_vra = 'ejurado@unicauca.edu.co'; // Email de VRA, obtener de BD si es necesario

foreach ($emails_a_enviar as $email_depto => $data) {
    $nombre_depto = $data['nombre_depto'];
    $solicitudes_para_correo = $data['solicitudes'];

    // 3. Construimos el cuerpo del correo con el formato de tabla que definiste.
    $email_body = "
        <p>Cordial saludo, </p>
        <p>La Facultad ha AVALADO y generado el oficio para las siguientes solicitudes de novedad de vinculación del departamento de <strong>{$nombre_depto}</strong>:</p>
        <table style='width:100%; border-collapse: collapse; margin-top: 15px;'>
            <thead>
                <tr style='background-color:#f2f2f2;'>
                    <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Profesor(a)</th>
                    <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Cédula</th>
                    <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Periodo</th>
                    <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Novedad</th>
                    <th style='border: 1px solid #ddd; padding: 8px; text-align: left;'>Observación</th>
                </tr>
            </thead>
            <tbody>
    ";

    foreach ($solicitudes_para_correo as $solicitud) {
        $obs_display = empty($solicitud['observacion_facultad']) ? "Sin observación." : htmlspecialchars($solicitud['observacion_facultad']);
        $email_body .= "
                <tr>
                    <td style='border: 1px solid #ddd; padding: 8px;'><strong>" . htmlspecialchars($solicitud['nombre']) . "</strong></td>
                    <td style='border: 1px solid #ddd; padding: 8px;'>" . htmlspecialchars($solicitud['cedula']) . "</td>
                    <td style='border: 1px solid #ddd; padding: 8px;'>" . htmlspecialchars($solicitud['anio_semestre']) . "</td>
                    <td style='border: 1px solid #ddd; padding: 8px;'>" . htmlspecialchars($solicitud['novedad']) . "</td>
                    <td style='border: 1px solid #ddd; padding: 8px;'>{$obs_display}</td>
                </tr>
        ";
    }

    $email_body .= "
            </tbody>
        </table>
        <p style='margin-top: 20px;'>El trámite continuará en la Vicerrectoría Académica. Para más detalles, por favor revise la plataforma: <a href='http://192.168.42.175/temporalesc/'>Sistema de Vinculación Temporal</a> <em>(acceso restringido a la red interna de la Universidad del Cauca)</em></p>
        <p>Universitariamente,</p>
        <p><strong>Decanatura de Facultad</strong></p>
    ";

    // 4. Configuramos y enviamos el correo usando PHPMailer
    $asunto = "Novedades Avaladas por Facultad - Dpto. de " . $nombre_depto;
    $mail = new PHPMailer(true);
    try {
        // --- Usamos la configuración que ya sabemos que funciona ---
        $mail->isSMTP();
        $mail->Host       = $config['smtp_host'];
        $mail->SMTPAuth   = true;
        $mail->Username   = $config['smtp_username'];
        $mail->Password   = $config['smtp_password'];
        $mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS;
        $mail->Port       = $config['smtp_port'];
        $mail->CharSet    = 'UTF-8';
        $mail->SMTPOptions = ['ssl' => ['verify_peer' => false, 'verify_peer_name' => false, 'allow_self_signed' => true]];

        // --- Remitente y Destinatarios ---
        $mail->setFrom($config['from_email'], $config['from_name']);
        $mail->addAddress($email_depto, $nombre_depto);
        $mail->addAddress($email_vra); // Con copia a VRA
        
        // --- Contenido del Correo ---
        $mail->isHTML(true);
        $mail->Subject = $asunto;
        $mail->Body    = $email_body;

        $mail->send();
    } catch (Exception $e) {
        error_log("PHPMailer Error en generar_word_solicitudes_seleccion.php: {$mail->ErrorInfo}");
    }
}
// ===== TERMINA EL NUEVO BLOQUE DE ENVÍO DE CORREO =====

// Configurar el nombre del archivo y las cabeceras para la descarga
$fileName = 'Novedades_' . $anio_semestre . '_Facultad_' . $nombre_facultad_principal . '_' . date('Ymd') . '.docx';
header('Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document');
header('Content-Disposition: attachment;filename="' . $fileName . '"');
header('Cache-Control: max-age=0');

// Guardar el documento en la salida
$objWriter = \PhpOffice\PhpWord\IOFactory::createWriter($phpWord, 'Word2007');
$objWriter->save('php://output');

// Cerrar la conexión a la base de datos
$conn->close();
?>