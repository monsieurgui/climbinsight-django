from django.shortcuts import render, get_object_or_404
from users.decorators import role_required
from django.views.generic import DetailView
from django.http import HttpRequest, HttpResponse
from datetime import datetime
import base64
import io
from .models import League, Category
from .dashboard import LeagueDashboard

# Create your views here.

@role_required(['ADMIN'])
def create_league(request):
    # Only admins can access this view
    pass

@role_required(['OFFICIAL'])
def score_competition(request):
    # Only officials can access this view
    pass

class LeagueDashboardView(DetailView):
    model = League
    template_name = 'leagues/dashboard.html'
    context_object_name = 'league'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        league = self.get_object()
        
        # Get filter parameters
        category_id = self.request.GET.get('category')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        # Initialize dashboard
        dashboard = LeagueDashboard(league)
        
        # Get category if specified
        category = None
        if category_id:
            category = get_object_or_404(Category, id=category_id)
        
        # Convert date strings to datetime objects
        start_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        end_date = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        
        # Generate plots and convert to base64
        def fig_to_base64(fig):
            buf = io.BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
        
        rankings_fig = dashboard.plot_rankings_over_time(category, start_date, end_date)
        points_fig = dashboard.plot_points_distribution(category)
        level_fig = dashboard.plot_competition_level_comparison(category)
        
        # Get performance summary and rankings
        summary = dashboard.get_performance_summary(category)
        rankings_df = dashboard.get_rankings_dataframe(category)
        
        context.update({
            'categories': Category.objects.all(),
            'selected_category': category,
            'start_date': start_date,
            'end_date': end_date,
            'summary': summary,
            'rankings': rankings_df.to_dict('records'),
            'rankings_chart': fig_to_base64(rankings_fig),
            'points_chart': fig_to_base64(points_fig),
            'level_chart': fig_to_base64(level_fig)
        })
        
        return context
