from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

@api_view(['GET'])
@permission_classes([AllowAny])
def index(request):
    """
    Serve the frontend SPA
    """
    return render(request, 'index.html')
