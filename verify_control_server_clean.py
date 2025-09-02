#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
verify_control_server_clean.py - Verificar que control_server.py está limpio

Verifica que se eliminaron todas las modificaciones relacionadas con:
1. Parámetros específicos por dirección de movimiento
2. Almacenamiento de velocidades
3. Detección de tipo de movimiento
4. Variables _last_vx, _last_vy, _last_wz
"""

import os
import sys

def check_control_server():
    """Verificar que control_server.py esté limpio"""
    
    control_server_path = os.path.join("robot_scripts", "control_server.py")
    
    if not os.path.exists(control_server_path):
        print("❌ No se encuentra control_server.py")
        return False
    
    print("📄 Verificando control_server.py...")
    
    with open(control_server_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Términos que NO deberían estar presentes
    forbidden_terms = [
        '_last_vx',
        '_last_vy', 
        '_last_wz',
        'movement_type',
        'detect_movement',
        'current_velocities',
        'MOVEMENT_SPECIFIC_PARAMS',
        'movement_params',
        'backward',
        'sideways',
        'rotation',
        'mixed',
        'globals()[\'_last_',
        'predict_gait_parameters(vx',
        'predict_gait_parameters(current_vx'
    ]
    
    # Verificar términos prohibidos
    found_issues = []
    for term in forbidden_terms:
        if term in content:
            found_issues.append(term)
    
    # Verificar que predict_gait_parameters() no tenga parámetros
    if 'predict_gait_parameters(' in content:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'predict_gait_parameters(' in line:
                if not 'predict_gait_parameters()' in line:
                    found_issues.append("predict_gait_parameters() con parámetros en línea {}".format(i+1))
    
    # Verificar que mantenga funcionalidad esencial
    required_terms = [
        'adaptive_walker.predict_gait_parameters()',
        'fallManager',
        'setAdaptiveMode',
        'getAdaptiveMode',
        'LightGBM AutoML adaptativo'
    ]
    
    missing_required = []
    for term in required_terms:
        if term not in content:
            missing_required.append(term)
    
    # Reportar resultados
    print("\n=== VERIFICACIÓN DE LIMPIEZA ===")
    
    if found_issues:
        print("❌ Se encontraron elementos que deberían eliminarse:")
        for issue in found_issues:
            print("  - {}".format(issue))
    else:
        print("✅ No se encontraron elementos prohibidos")
    
    if missing_required:
        print("\n❌ Faltan elementos esenciales:")
        for missing in missing_required:
            print("  - {}".format(missing))
    else:
        print("✅ Todos los elementos esenciales están presentes")
    
    # Verificar funcionalidades mantenidas
    print("\n=== FUNCIONALIDADES MANTENIDAS ===")
    
    maintained_features = [
        ("Sistema dual-mode", "setAdaptiveMode" in content and "getAdaptiveMode" in content),
        ("Control Fall Manager", "fallManager" in content),
        ("LightGBM AutoML", "adaptive_walker.predict_gait_parameters()" in content),
        ("WebSocket handlers", "elif action ==" in content),
        ("Logging system", "logger.info" in content)
    ]
    
    for feature, present in maintained_features:
        status = "✅" if present else "❌"
        print("{} {}".format(status, feature))
    
    # Resultado final
    is_clean = len(found_issues) == 0 and len(missing_required) == 0
    
    if is_clean:
        print("\n🎉 CONTROL_SERVER.PY ESTÁ LIMPIO")
        print("✅ Eliminadas todas las modificaciones de parámetros específicos por dirección")
        print("✅ Mantenidas todas las funcionalidades esenciales")
        print("✅ Listo para usar predict_gait_parameters() sin parámetros")
    else:
        print("\n⚠️ CONTROL_SERVER.PY NECESITA AJUSTES")
    
    return is_clean

def main():
    """Función principal"""
    print("=== VERIFICACIÓN DE LIMPIEZA DE CONTROL_SERVER.PY ===")
    print("Objetivo: Confirmar eliminación de parámetros específicos por dirección")
    
    success = check_control_server()
    
    if success:
        print("\n📋 SIGUIENTE PASO:")
        print("1. Transferir control_server.py al NAO")
        print("2. El sistema usará solo modo production/training básico")
        print("3. predict_gait_parameters() sin parámetros de velocidad")
        print("4. Control Fall Manager mantiene funcionalidad mejorada")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
