from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Municipality(models.TextChoices):
    AILEU = 'AILEU', _('Aileu')
    AINARO = 'AINARO', _('Ainaro')
    BAUCAU = 'BAUCAU', _('Baucau')
    BOBONARO = 'BOBONARO', _('Bobonaro')
    COVA_LIMA = 'COVA_LIMA', _('Cova Lima')
    DILI = 'DILI', _('Dili')
    ERMERA = 'ERMERA', _('Ermera')
    LAUTEM = 'LAUTEM', _('Lautem')
    LIQUICA = 'LIQUICA', _('Liquica')
    MANATUTO = 'MANATUTO', _('Manatuto')
    MANUFAHI = 'MANUFAHI', _('Manufahi')
    OECUSSE = 'OECUSSE', _('Oecusse')
    VIQUEQUE = 'VIQUEQUE', _('Viqueque')


class WeatherStation(models.Model):
    class StationType(models.TextChoices):
        AWS = 'AWS', _('Automated Weather Station (AWS)')
        AWOS = 'AWOS', _('Automated Weather Observing System (AWOS)')
        SYNOPTIC = 'SYNOPTIC', _('Synoptic Station')
        TIDE_GAUGE = 'TIDE_GAUGE', _('Tide Gauge Station')
        BUOY = 'BUOY', _('Marine Buoy Station')
        AGROMET = 'AGROMET', _('Agrometeorological Station')
        HYDROMET = 'HYDROMET', _('Hydrometeorological Station')
        SEISMIC = 'SEISMIC', _('Seismic Monitoring Station')

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        MAINTENANCE = 'MAINTENANCE', _('Under Maintenance')
        INACTIVE = 'INACTIVE', _('Inactive')

    external_id = models.IntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text=_("API ID e.g., 15401"),
        verbose_name=_("External API ID")
    )
    name = models.CharField(max_length=150, verbose_name=_('Station Name'))
    code = models.CharField(max_length=30, unique=True, verbose_name=_('Station Code'))
    municipality = models.CharField(
        max_length=30,
        choices=Municipality.choices,
        default=Municipality.DILI,
        verbose_name=_('Municipality')
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name=_('Latitude'))
    longitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name=_('Longitude'))
    elevation = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Elevation (m)')
    )
    station_type = models.CharField(
        max_length=20,
        choices=StationType.choices,
        default=StationType.AWS,
        verbose_name=_('Station Type')
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_('Status')
    )
    installed_date = models.DateField(null=True, blank=True, verbose_name=_('Installed Date'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Weather Station')
        verbose_name_plural = _('Weather Stations')
        constraints = [
            models.CheckConstraint(
                condition=Q(municipality__in=Municipality.values),
                name='weather_station_municipality_valid',
            ),
            models.CheckConstraint(
                condition=Q(station_type__in=[
                    'AWS', 'AWOS', 'SYNOPTIC', 'TIDE_GAUGE', 'BUOY', 'AGROMET',
                    'HYDROMET', 'SEISMIC',
                ]),
                name='weather_station_type_valid',
            ),
            models.CheckConstraint(
                condition=Q(status__in=['ACTIVE', 'MAINTENANCE', 'INACTIVE']),
                name='weather_station_status_valid',
            ),
            models.CheckConstraint(
                condition=Q(latitude__gte=-90) & Q(latitude__lte=90),
                name='weather_station_latitude_range',
            ),
            models.CheckConstraint(
                condition=Q(longitude__gte=-180) & Q(longitude__lte=180),
                name='weather_station_longitude_range',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.get_municipality_display()}"


class WeatherObservation(models.Model):
    station = models.ForeignKey(
        WeatherStation,
        on_delete=models.CASCADE,
        related_name='observations',
        verbose_name=_('Station')
    )
    temperature = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Temperature (°C)')
    )
    humidity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_('Humidity (%)'))
    rainfall_mm = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Rainfall (mm)')
    )
    wind_speed_kmh = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Wind Speed (km/h)')
    )
    wind_direction = models.CharField(max_length=20, blank=True, verbose_name=_('Wind Direction'))
    pressure_hpa = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Pressure (hPa)')
    )
    wave_height_m = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Wave Height (m)')
    )
    tide_level_mm = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Tide Level (mm)')
    )
    peak_period_s = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Peak Period (s)')
    )
    solar_radiation = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Solar Radiation (W/m²)')
    )
    wind_gust_kmh = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Max Wind Gust (km/h)')
    )
    sea_surface_temp = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Sea Surface Temp (°C)')
    )
    battery_voltage = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Battery Voltage (V)')
    )
    condition_text = models.CharField(max_length=100, blank=True, verbose_name=_('Condition Description'))
    recorded_at = models.DateTimeField(verbose_name=_('Recorded At'))
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='observations',
        verbose_name=_('Recorded By')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = _('Weather Observation')
        verbose_name_plural = _('Weather Observations')
        indexes = [
            models.Index(fields=['station', '-recorded_at'], name='weather_obs_station_time_idx'),
        ]

    def __str__(self):
        return f"{self.station.code} @ {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"


class WeatherForecast(models.Model):
    municipality = models.CharField(
        max_length=30,
        choices=Municipality.choices,
        verbose_name=_('Municipality')
    )
    forecast_date = models.DateField(verbose_name=_('Forecast Date'))
    temp_min = models.IntegerField(verbose_name=_('Min Temperature (°C)'))
    temp_max = models.IntegerField(verbose_name=_('Max Temperature (°C)'))
    condition = models.CharField(max_length=100, verbose_name=_('Condition'))
    icon = models.CharField(
        max_length=50,
        default='cloud-sun',
        verbose_name=_('Icon Class (Bootstrap)'),
        help_text=_('Bootstrap icon name e.g., sun, cloud-rain, cloud-lightning, cloud-sun')
    )
    rain_probability = models.IntegerField(default=0, verbose_name=_('Rainfall Probability (%)'))
    wind_summary = models.CharField(max_length=50, blank=True, verbose_name=_('Wind Summary'))
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forecasts',
        verbose_name=_('Issued By')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['forecast_date', 'municipality']
        verbose_name = _('Weather Forecast')
        verbose_name_plural = _('Weather Forecasts')
        constraints = [
            models.UniqueConstraint(
                fields=['municipality', 'forecast_date'],
                name='weather_forecast_municipality_date_unique',
            ),
            models.CheckConstraint(
                condition=Q(municipality__in=Municipality.values),
                name='weather_forecast_municipality_valid',
            ),
            models.CheckConstraint(
                condition=Q(temp_min__lte=F('temp_max')),
                name='weather_forecast_temperature_range',
            ),
            models.CheckConstraint(
                condition=Q(rain_probability__gte=0) & Q(rain_probability__lte=100),
                name='weather_forecast_rain_probability_range',
            ),
        ]

    def __str__(self):
        return f"{self.get_municipality_display()} - {self.forecast_date}: {self.condition}"


class EarlyWarningQuerySet(models.QuerySet):
    """Reusable public-visibility rules for time-bound early warnings."""

    def currently_public(self, at=None):
        at = at or timezone.now()
        return self.filter(is_active=True, valid_from__lte=at, valid_to__gte=at)


class EarlyWarning(models.Model):
    class Severity(models.TextChoices):
        INFO = 'info', _('Information / Advisory')
        WARNING = 'warning', _('Warning (Orange Alert)')
        DANGER = 'danger', _('Severe Hazard Alert (Red Alert)')

    objects = EarlyWarningQuerySet.as_manager()

    title = models.CharField(max_length=255, verbose_name=_('Warning Title'))
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.WARNING,
        verbose_name=_('Severity Level')
    )
    region = models.CharField(
        max_length=255,
        verbose_name=_('Affected Region / Municipalities'),
        help_text=_('e.g., Viqueque & Lautem Municipalities, All Coastal Areas')
    )
    description = models.TextField(verbose_name=_('Detailed Advisory Content'))
    valid_from = models.DateTimeField(verbose_name=_('Valid From'))
    valid_to = models.DateTimeField(verbose_name=_('Valid Until'))
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='warnings',
        verbose_name=_('Issued By')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Early Warning')
        verbose_name_plural = _('Early Warnings')
        constraints = [
            models.CheckConstraint(
                condition=Q(severity__in=['info', 'warning', 'danger']),
                name='weather_warning_severity_valid',
            ),
            models.CheckConstraint(
                condition=Q(valid_to__gt=F('valid_from')),
                name='weather_warning_validity_range',
            ),
        ]
        indexes = [
            models.Index(fields=['is_active', '-valid_from'], name='weather_warning_active_idx'),
        ]

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title}"

    @property
    def publication_state(self):
        """Return the public visibility state used by staff-facing status labels."""
        if not self.is_active:
            return "archived"
        current_time = timezone.now()
        if self.valid_from > current_time:
            return "scheduled"
        if self.valid_to < current_time:
            return "expired"
        return "live"
