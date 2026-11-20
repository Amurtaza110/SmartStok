"""
SmartStock Inventory Forms
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Field

from .models import CustomUser, Product, Category, Supplier, StockMovement


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'role', 'password1', 'password2')


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'generic_name', 'description', 'tags',
            'barcode', 'category', 'supplier',
            'purchase_price', 'selling_price', 'unit',
            'min_stock', 'reorder_point', 'current_stock',
            'expiry_date', 'batch_number', 'image',
        ]
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.TextInput(attrs={'placeholder': 'fever, pain, antibiotic'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(Column('name', css_class='col-md-8'),
                Column('barcode', css_class='col-md-4')),
            Row(Column('generic_name', css_class='col-md-6'),
                Column('tags', css_class='col-md-6')),
            'description',
            Row(Column('category', css_class='col-md-6'),
                Column('supplier', css_class='col-md-6')),
            Row(Column('purchase_price', css_class='col-md-4'),
                Column('selling_price', css_class='col-md-4'),
                Column('unit', css_class='col-md-4')),
            Row(Column('current_stock', css_class='col-md-4'),
                Column('min_stock', css_class='col-md-4'),
                Column('reorder_point', css_class='col-md-4')),
            Row(Column('expiry_date', css_class='col-md-6'),
                Column('batch_number', css_class='col-md-6')),
            'image',
            Submit('submit', 'Save Product', css_class='btn btn-primary mt-2'),
        )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'icon']


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact', 'email', 'address', 'city']


class SaleForm(forms.ModelForm):
    class Meta:
        model = None  # handled manually via POS
        fields = []


class StockAdjustmentForm(forms.Form):
    MOVEMENT_CHOICES = (
        ('IN',      'Add Stock (Purchase/Return)'),
        ('OUT',     'Remove Stock'),
        ('ADJUST',  'Set Exact Quantity'),
        ('EXPIRED', 'Remove Expired Items'),
    )
    movement_type = forms.ChoiceField(choices=MOVEMENT_CHOICES, label='Adjustment Type')
    quantity = forms.IntegerField(min_value=1, label='Quantity')
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label='Notes / Reason'
    )
