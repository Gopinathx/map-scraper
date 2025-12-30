from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from rest_framework import generics
from .models import Business, ScrapeAction
from .serializers import BusinessSerializer
from rest_framework.permissions import IsAuthenticated
import threading
from django.contrib import admin, messages
from .scraper import scrape_google_maps
from django.core.paginator import Paginator
import csv
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch

# Registration View
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Log the user in after they register
            return redirect('dashboard') # Redirect to a dashboard or home
    else:
        form = UserCreationForm()
    return render(request, 'main/register.html', {'form': form})

# A protected view (only for logged-in users)
@login_required
def dashboard(request):
    return render(request, 'main/dashboard.html')


class BusinessListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    queryset = Business.objects.all().order_by('-created_at')
    serializer_class = BusinessSerializer

# This view handles GET (one), PUT (update), and DELETE
class BusinessDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer


@login_required
def start_scrape(request):
    if request.method == 'POST':
        keyword = request.POST.get('keyword')
        limit = request.POST.get('limit', 10)
        user_id = request.user.id
        
        if keyword:
            # We run this in a Thread so the website doesn't freeze
            thread = threading.Thread(target=scrape_google_maps, args=(keyword,user_id,int(limit)))
            thread.start()
            
            messages.success(request, f"Scraper started for '{keyword}'. Refresh in a minute to see results!")
        return redirect('dashboard')
    
    return redirect('dashboard')


@login_required
def dashboard(request):
    # 1. Get unique scrape sessions (The Folders)
    all_history = ScrapeAction.objects.filter(user=request.user).order_by('-created_at')
    
    # 2. Determine which group to display (Default to the latest one)
    selected_id = request.GET.get('action_id')
    if selected_id:
        active_group = all_history.filter(id=selected_id).first()
    else:
        active_group = all_history.first()

    # 3. Get results only for that specific group
    if active_group:
        # Pull only the 10, 20, or 50 rows belonging to this search
        business_list = active_group.results.all().order_by('id')
    else:
        business_list = Business.objects.none()

    # 4. Filter within the active group
    query = request.GET.get('q')
    if query:
        business_list = business_list.filter(name__icontains=query)

    paginator = Paginator(business_list, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'main/dashboard.html', {
        'page_obj': page_obj,
        'all_history': all_history,
        'active_group': active_group,
        'scrape_count': all_history.count()
    })



def export_businesses_csv(request):
    # 1. Get the action_id from the URL parameters
    action_id = request.GET.get('action_id')
    
    response = HttpResponse(content_type='text/csv')
    
    if action_id:
        # Filter businesses belonging to the specific mission
        businesses = Business.objects.filter(action_id=action_id)
        # Dynamic filename based on the mission keyword if available
        mission = ScrapeAction.objects.filter(id=action_id).first()
        filename = f"{mission.keyword.replace(' ', '_')}_leads.csv" if mission else "scraped_leads.csv"
    else:
        # Fallback: export all if no specific mission is selected
        businesses = Business.objects.all()
        filename = "all_scraped_leads.csv"

    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'Address', 'Website', 'Phone', 'Category', 'Lat', 'Lng'])

    # Write only the filtered rows
    for b in businesses:
        writer.writerow([b.name, b.address, b.website, b.phone_number, b.category, b.latitude, b.longitude])

    return response

def export_businesses_pdf(request):
    action_id = request.GET.get('action_id')
    response = HttpResponse(content_type='application/pdf')
    
    # 1. Fetch Data
    if action_id:
        mission = ScrapeAction.objects.filter(id=action_id).first()
        businesses = Business.objects.filter(action_id=action_id)
        filename = f"{mission.keyword.replace(' ', '_')}.pdf"
    else:
        businesses = Business.objects.all()
        filename = "all_leads.pdf"

    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # 2. Setup PDF (Landscape often works better for tables)
    doc = SimpleDocTemplate(response, pagesize=landscape(letter), 
                            rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Create a custom style for the links
    link_style = styles['Normal'].clone('LinkStyle')
    link_style.fontSize = 8
    link_style.textColor = colors.blue

    # Header Text
    title = f"Leads Report: {mission.keyword if action_id else 'All Leads'}"
    elements.append(Paragraph(title, styles['Title']))
    elements.append(Paragraph(f"Total Records: {businesses.count()}", styles['Normal']))
    elements.append(Paragraph("<br/><br/>", styles['Normal']))

    # 3. Create Table Data with Clickable Links
    # Using Paragraphs inside cells allows for text wrapping and clickable anchors
    data = [['Name', 'Phone', 'Website', 'Category']] 
    
    for b in businesses:
        name = Paragraph(b.name or "N/A", styles['Normal'])
        phone = b.phone_number or "N/A"
        category = Paragraph(b.category or "N/A", styles['Normal'])
        
        # Make Website Clickable
        if b.website:
            url = b.website if b.website.startswith('http') else f'http://{b.website}'
            website_link = Paragraph(f'<a href="{url}" color="blue"><u>{b.website[:40]}</u></a>', link_style)
        else:
            website_link = "N/A"
            
        data.append([name, phone, website_link, category])

    # 4. Table Alignment and Column Widths
    # Total width for landscape letter is ~10 inches
    t = Table(data, colWidths=[3*inch, 1.5*inch, 3.5*inch, 2*inch], repeatRows=1)
    
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.indigo),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), # Align to top for better wrapping look
    ]))

    elements.append(t)
    doc.build(elements)
    return response