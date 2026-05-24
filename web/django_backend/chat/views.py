
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import requests
import json

FASTAPI_BASE_URL = settings.FASTAPI_BASE_URL


def _proxy_request(method, url, data=None, params=None, timeout=30):
    """通用代理请求方法"""
    try:
        if method == 'GET':
            response = requests.get(url, params=params, timeout=timeout)
        elif method == 'POST':
            response = requests.post(url, json=data, timeout=timeout)
        elif method == 'PUT':
            response = requests.put(url, json=data, timeout=timeout)
        elif method == 'DELETE':
            response = requests.delete(url, timeout=timeout)
        else:
            return JsonResponse({'error': 'Unsupported method'}, status=405)

        if response.status_code == 204:
            return JsonResponse({}, status=204)

        return JsonResponse(response.json(), status=response.status_code, safe=False)
    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': f'Upstream service error: {str(e)}'}, status=502)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def proxy_chat(request):
    data = json.loads(request.body.decode('utf-8'))
    return _proxy_request('POST', f'{FASTAPI_BASE_URL}/api/v1/chat', data=data, timeout=120)


@csrf_exempt
@require_http_methods(["GET"])
def proxy_health(request):
    return _proxy_request('GET', f'{FASTAPI_BASE_URL}/health', timeout=5)


@csrf_exempt
@require_http_methods(["GET"])
def proxy_task_status(request, task_id):
    return _proxy_request('GET', f'{FASTAPI_BASE_URL}/api/v1/tasks/{task_id}', timeout=30)


# =============================================================================
# 对话管理代理 API
# =============================================================================

@csrf_exempt
@require_http_methods(["GET", "POST"])
def proxy_conversations(request):
    """对话列表 - GET获取列表, POST创建新对话"""
    if request.method == 'GET':
        params = {}
        if request.GET.get('user_id'):
            params['user_id'] = request.GET.get('user_id')
        if request.GET.get('limit'):
            params['limit'] = request.GET.get('limit')
        if request.GET.get('offset'):
            params['offset'] = request.GET.get('offset')
        return _proxy_request('GET', f'{FASTAPI_BASE_URL}/api/v1/conversations', params=params)
    else:  # POST
        data = json.loads(request.body.decode('utf-8'))
        return _proxy_request('POST', f'{FASTAPI_BASE_URL}/api/v1/conversations', data=data)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def proxy_conversation_detail(request, conversation_id):
    """对话详情 - GET获取详情, PUT更新, DELETE删除"""
    if request.method == 'GET':
        return _proxy_request('GET', f'{FASTAPI_BASE_URL}/api/v1/conversations/{conversation_id}')
    elif request.method == 'PUT':
        data = json.loads(request.body.decode('utf-8'))
        return _proxy_request('PUT', f'{FASTAPI_BASE_URL}/api/v1/conversations/{conversation_id}', data=data)
    else:  # DELETE
        return _proxy_request('DELETE', f'{FASTAPI_BASE_URL}/api/v1/conversations/{conversation_id}')


@csrf_exempt
@require_http_methods(["POST"])
def proxy_add_message(request, conversation_id):
    """添加消息到对话"""
    data = json.loads(request.body.decode('utf-8'))
    return _proxy_request('POST', f'{FASTAPI_BASE_URL}/api/v1/conversations/{conversation_id}/messages', data=data)


@csrf_exempt
@require_http_methods(["POST"])
def proxy_summarize_conversation(request, conversation_id):
    """生成对话总结和标题"""
    return _proxy_request('POST', f'{FASTAPI_BASE_URL}/api/v1/conversations/{conversation_id}/summarize')
