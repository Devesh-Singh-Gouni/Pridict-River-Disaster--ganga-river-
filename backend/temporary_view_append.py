
# ===============================
# FRONTEND VIEWS
# ===============================
@api_view(['GET'])
@permission_classes([AllowAny])
def index(request):
    """
    Serve the frontend SPA
    """
    return render(request, 'index.html')
