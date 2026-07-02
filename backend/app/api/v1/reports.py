"""Reports API endpoints — generate, list, and export reports.

Routes
------
GET  /api/v1/reports                  — list all reports for district
POST /api/v1/reports                  — generate a new report
GET  /api/v1/reports/<id>             — get report detail + data
GET  /api/v1/reports/<id>/export/pdf  — download report as PDF
GET  /api/v1/reports/<id>/export/excel— download report as Excel
"""
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, g, Response
from flask_jwt_extended import get_jwt

from app.models.report import Report
from app.services.analytics.report_generator import generate_report, export_pdf, export_excel
from app.services.rbac_service import require_permission
from app.services.social.report_exports import (
    COMMENTS_FILENAME,
    COMPLAINTS_FILENAME,
    MONTHLY_SOCIAL_FILENAME,
    export_comments_excel,
    export_complaints_excel,
    export_monthly_social_pdf,
)
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

VALID_REPORT_TYPES = {'daily', 'weekly', 'monthly', 'executive', 'custom'}


def _district():
    return get_jwt().get('district_id', '')


def _download(payload: bytes, mimetype: str, filename: str) -> Response:
    return Response(
        payload,
        mimetype=mimetype,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )

@reports_bp.route('', methods=['GET'])
@require_permission('report', 'read')
def list_reports():
    """List all reports for the current district, newest first.

    Query params: ``page``, ``per_page``, ``report_type``, ``status``.
    """
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    query = Report.query.filter_by(district_id=_district())

    report_type = request.args.get('report_type')
    if report_type:
        query = query.filter(Report.report_type == report_type)

    status = request.args.get('status')
    if status:
        query = query.filter(Report.status == status)

    pagination = query.order_by(Report.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return paginated_response([r.to_dict() for r in pagination.items], pagination)


@reports_bp.route('', methods=['POST'])
@require_permission('report', 'create')
def create_report():
    """Generate a new report.

    Request body (JSON)::

        {
          "report_type": "weekly",
          "period_start": "2026-06-01",   // required only for custom/executive
          "period_end":   "2026-06-30"
        }
    """
    data = request.get_json(silent=True) or {}
    report_type = data.get('report_type', '').strip()

    if not report_type:
        return error_response('report_type is required.', 400, 'VALIDATION_ERROR')
    if report_type not in VALID_REPORT_TYPES:
        return error_response(
            f"report_type must be one of: {', '.join(VALID_REPORT_TYPES)}",
            400, 'VALIDATION_ERROR',
        )

    try:
        report = generate_report(
            district_id=_district(),
            report_type=report_type,
            generated_by=g.current_user.id,
            period_start=data.get('period_start'),
            period_end=data.get('period_end'),
        )
        return success_response(
            data=report.to_dict(),
            status_code=201,
            message=f'{report_type.capitalize()} report generated.',
        )
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')
    except Exception as exc:
        logger.exception('Report generation failed')
        return error_response(str(exc), 500, 'REPORT_GENERATION_FAILED')


@reports_bp.route('/export/comments/excel', methods=['GET'])
@require_permission('report', 'read')
def download_comments_report():
    """Download all collector comments as comments_report.xlsx."""
    try:
        return _download(
            export_comments_excel(_district()),
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            COMMENTS_FILENAME,
        )
    except Exception as exc:
        logger.exception('Comments Excel export failed')
        return error_response(str(exc), 500, 'EXPORT_FAILED')


@reports_bp.route('/export/complaints/excel', methods=['GET'])
@require_permission('report', 'read')
def download_complaints_report():
    """Download complaint-only collector data as complaints_report.xlsx."""
    try:
        return _download(
            export_complaints_excel(_district()),
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            COMPLAINTS_FILENAME,
        )
    except Exception as exc:
        logger.exception('Complaints Excel export failed')
        return error_response(str(exc), 500, 'EXPORT_FAILED')


@reports_bp.route('/export/monthly-social/pdf', methods=['GET'])
@require_permission('report', 'read')
def download_monthly_social_report():
    """Download the monthly social report as monthly_social_report.pdf."""
    try:
        return _download(
            export_monthly_social_pdf(_district()),
            'application/pdf',
            MONTHLY_SOCIAL_FILENAME,
        )
    except Exception as exc:
        logger.exception('Monthly social PDF export failed')
        return error_response(str(exc), 500, 'EXPORT_FAILED')

@reports_bp.route('/<report_id>', methods=['GET'])
@require_permission('report', 'read')
def get_report(report_id):
    """Get full report data including analytics payload."""
    report = Report.query.filter_by(id=report_id, district_id=_district()).first()
    if not report:
        return error_response('Report not found.', 404, 'NOT_FOUND')
    return success_response(data=report.to_dict())


@reports_bp.route('/<report_id>/export/pdf', methods=['GET'])
@require_permission('report', 'read')
def download_pdf(report_id):
    """Download the report as a PDF file."""
    report = Report.query.filter_by(id=report_id, district_id=_district()).first()
    if not report:
        return error_response('Report not found.', 404, 'NOT_FOUND')
    if report.status != 'ready':
        return error_response(f"Report status is '{report.status}' — cannot export.", 400, 'REPORT_NOT_READY')

    try:
        pdf_bytes = export_pdf(report)
        filename  = f"report_{report.report_type}_{report.period_start}_{report.period_end}.pdf"
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.exception('PDF export failed for report %s', report_id)
        return error_response(str(exc), 500, 'EXPORT_FAILED')


@reports_bp.route('/<report_id>/export/excel', methods=['GET'])
@require_permission('report', 'read')
def download_excel(report_id):
    """Download the report as an Excel (.xlsx) file."""
    report = Report.query.filter_by(id=report_id, district_id=_district()).first()
    if not report:
        return error_response('Report not found.', 404, 'NOT_FOUND')
    if report.status != 'ready':
        return error_response(f"Report status is '{report.status}' — cannot export.", 400, 'REPORT_NOT_READY')

    try:
        excel_bytes = export_excel(report)
        filename = f"report_{report.report_type}_{report.period_start}_{report.period_end}.xlsx"
        return Response(
            excel_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.exception('Excel export failed for report %s', report_id)
        return error_response(str(exc), 500, 'EXPORT_FAILED')


