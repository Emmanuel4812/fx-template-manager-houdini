"""
Validador de estructura de templates
Diagnóstico para verificar que los templates están correctamente estructurados
"""

import os
import sys
from pathlib import Path
from typing import Dict, List


class TemplateValidator:
    """Valida la estructura de templates"""

    def __init__(self, templates_path: str):
        self.path = Path(templates_path)
        self.issues = []
        self.valid_templates = []
        self.warnings = []

    def validate(self) -> Dict:
        """Valida todos los templates y retorna reporte"""

        if not self.path.exists():
            return {
                "success": False,
                "error": f"Ruta no existe: {self.path}",
                "valid_templates": [],
                "issues": [],
                "warnings": []
            }

        self.issues = []
        self.warnings = []
        self.valid_templates = []

        print(f"\n{'='*60}")
        print(f"Validando templates en: {self.path}")
        print(f"{'='*60}\n")

        for template_dir in sorted(self.path.iterdir()):
            if template_dir.is_dir() and not template_dir.name.startswith('.'):
                self._validate_template(template_dir)

        return self._generate_report()

    def _validate_template(self, template_path: Path):
        """Valida un template individual"""

        template_name = template_path.name
        print(f"Validando: {template_name}", end=" ... ")

        # Buscar .hip
        hip_files = list(template_path.glob("*.hip"))

        if not hip_files:
            self.issues.append(f"{template_name}: No contiene archivos .hip")
            print("❌ SIN ARCHIVO .HIP")
            return

        # Verificar preview
        preview_file = self._find_preview(template_path)

        if not preview_file:
            self.warnings.append(f"{template_name}: No tiene preview (videos/imagenes)")
            print("✓ (sin preview)")
        else:
            print(f"✓ ({preview_file.suffix})")

        # Template válido
        self.valid_templates.append({
            "name": template_name,
            "hip_file": hip_files[0].name,
            "hip_count": len(hip_files),
            "preview": preview_file.name if preview_file else None,
            "path": str(template_path)
        })

        # Warnings adicionales
        if len(hip_files) > 1:
            extra = len(hip_files) - 1
            self.warnings.append(
                f"{template_name}: Contiene {extra} archivos .hip adicionales"
            )

    def _find_preview(self, template_path: Path) -> Path | None:
        """Busca archivos de preview en el template"""

        # Buscar en carpetas comunes
        for video_dir in ['video', 'videos', 'preview', 'previews']:
            video_path = template_path / video_dir
            if video_path.exists():
                for ext in ['*.mp4', '*.mov', '*.avi', '*.webm', '*.png', '*.jpg', '*.exr']:
                    for file in video_path.glob(ext):
                        return file

        # Buscar en raíz
        for ext in ['*.mp4', '*.mov', '*.avi', '*.png', '*.jpg']:
            for file in template_path.glob(ext):
                return file

        return None

    def _generate_report(self) -> Dict:
        """Genera reporte de validación"""

        print(f"\n{'='*60}")
        print("REPORTE DE VALIDACIÓN")
        print(f"{'='*60}\n")

        print(f"✓ Templates válidos: {len(self.valid_templates)}")
        print(f"❌ Errores: {len(self.issues)}")
        print(f"⚠️  Warnings: {len(self.warnings)}")

        if self.valid_templates:
            print(f"\n{'TEMPLATES VÁLIDOS':^60}")
            print("-" * 60)
            for t in self.valid_templates:
                print(f"\n  📁 {t['name']}")
                print(f"     Archivo: {t['hip_file']}")
                if t['hip_count'] > 1:
                    print(f"     (+{t['hip_count'] - 1} más)")
                if t['preview']:
                    print(f"     Preview: {t['preview']}")
                else:
                    print(f"     Preview: ❌ None")

        if self.issues:
            print(f"\n{'ERRORES (FIX REQUERIDO)':^60}")
            print("-" * 60)
            for issue in self.issues:
                print(f"  ❌ {issue}")

        if self.warnings:
            print(f"\n{'WARNINGS':^60}")
            print("-" * 60)
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")

        print(f"\n{'='*60}\n")

        return {
            "success": len(self.issues) == 0,
            "valid_count": len(self.valid_templates),
            "error_count": len(self.issues),
            "warning_count": len(self.warnings),
            "valid_templates": self.valid_templates,
            "issues": self.issues,
            "warnings": self.warnings
        }


def generate_html_report(validation_result: Dict, output_file: str = "template_report.html"):
    """Genera un reporte HTML visual"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>FX Template Validation Report</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell; background: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 1000px; margin: 0 auto; background: white; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; margin-bottom: 10px; }}
            .header {{ margin-bottom: 30px; border-bottom: 2px solid #eee; padding-bottom: 20px; }}
            .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }}
            .stat-box {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
            .stat-box.success {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
            .stat-box.error {{ background: linear-gradient(135deg, #ee0979 0%, #ff6a00 100%); }}
            .stat-box.warning {{ background: linear-gradient(135deg, #f5af19 0%, #f12711 100%); }}
            .stat-number {{ font-size: 32px; font-weight: bold; }}
            .stat-label {{ font-size: 12px; opacity: 0.9; }}
            .section {{ margin-bottom: 30px; }}
            .section-title {{ font-size: 18px; font-weight: bold; color: #333; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #ddd; }}
            .template-card {{ background: #f9f9f9; padding: 15px; margin-bottom: 15px; border-left: 4px solid #667eea; border-radius: 4px; }}
            .template-card.valid {{ border-left-color: #11998e; }}
            .template-name {{ font-weight: bold; color: #333; font-size: 16px; }}
            .template-info {{ margin-top: 10px; font-size: 13px; color: #666; }}
            .template-info > div {{ margin-top: 5px; }}
            .icon {{ display: inline-block; width: 20px; text-align: center; margin-right: 8px; }}
            .error-item, .warning-item {{ padding: 12px; margin-bottom: 10px; border-radius: 4px; border-left: 4px solid #ff6a00; background: #fff5f0; }}
            .error-item {{ border-left-color: #ff0000; background: #ffe0e0; }}
            .warning-item {{ border-left-color: #ffc107; background: #fff8e1; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>FX Templates Validation Report</h1>
                <p style="color: #666;">Generated: {Path.cwd()}</p>
            </div>

            <div class="stats">
                <div class="stat-box success">
                    <div class="stat-number">{validation_result['valid_count']}</div>
                    <div class="stat-label">Valid Templates</div>
                </div>
                <div class="stat-box error">
                    <div class="stat-number">{validation_result['error_count']}</div>
                    <div class="stat-label">Errors</div>
                </div>
                <div class="stat-box warning">
                    <div class="stat-number">{validation_result['warning_count']}</div>
                    <div class="stat-label">Warnings</div>
                </div>
                <div class="stat-box {'success' if validation_result['success'] else 'error'}">
                    <div class="stat-number">{"✓" if validation_result['success'] else "✗"}</div>
                    <div class="stat-label">Overall Status</div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">✓ Valid Templates ({len(validation_result['valid_templates'])})</div>
    """

    for template in validation_result['valid_templates']:
        preview_info = f"<div><span class='icon'>🎥</span>{template['preview']}</div>" if template['preview'] else "<div><span class='icon'>❌</span>No preview</div>"

        html += f"""
        <div class="template-card valid">
            <div class="template-name">📁 {template['name']}</div>
            <div class="template-info">
                <div><span class="icon">📄</span>{template['hip_file']}</div>
                {preview_info}
            </div>
        </div>
        """

    if validation_result['issues']:
        html += f"""
        <div class="section">
            <div class="section-title">❌ Errors ({len(validation_result['issues'])})</div>
        """
        for issue in validation_result['issues']:
            html += f'<div class="error-item">{issue}</div>'
        html += "</div>"

    if validation_result['warnings']:
        html += f"""
        <div class="section">
            <div class="section-title">⚠️ Warnings ({len(validation_result['warnings'])})</div>
        """
        for warning in validation_result['warnings']:
            html += f'<div class="warning-item">{warning}</div>'
        html += "</div>"

    html += """
        </div>
    </body>
    </html>
    """

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ Reporte HTML generado: {output_file}\n")


if __name__ == "__main__":
    # Usar ruta por defecto o del argumento
    template_path = sys.argv[1] if len(sys.argv) > 1 else r"D:\escenasHoudiniRecursosVarios"

    validator = TemplateValidator(template_path)
    result = validator.validate()

    # Generar reporte HTML
    generate_html_report(result)

    # Exit code según resultado
    sys.exit(0 if result['success'] else 1)
