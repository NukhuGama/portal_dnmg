from django.db import models
from django.db.models import F, Q
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
    class CoordinateSource(models.TextChoices):
        MANUAL = 'MANUAL', _('Set manually in Admin DNMG')
        PROVIDER = 'PROVIDER', _('Updated from station provider')

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
    coordinate_source = models.CharField(
        max_length=12,
        choices=CoordinateSource.choices,
        default=CoordinateSource.MANUAL,
        verbose_name=_('Coordinate Source'),
        help_text=_('Manual coordinates are kept when live station data is synchronized.'),
    )
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
                condition=Q(coordinate_source__in=['MANUAL', 'PROVIDER']),
                name='weather_station_coordinate_source_valid',
            ),
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
    dew_point_c = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Dew Point (°C)'),
    )
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
    visibility_m = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Visibility (m)'),
    )
    runway_visual_range_m = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('Runway Visual Range (m)'),
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


class AwosMetarReport(models.Model):
    """A raw METAR copied from the Dili AWOS for operational display/history."""

    station = models.ForeignKey(
        WeatherStation,
        on_delete=models.CASCADE,
        related_name='awos_metar_reports',
        verbose_name=_('Station'),
    )
    reported_at = models.DateTimeField(verbose_name=_('Reported At'))
    raw_report = models.CharField(max_length=1000, verbose_name=_('Raw METAR'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-reported_at']
        verbose_name = _('AWOS METAR Report')
        verbose_name_plural = _('AWOS METAR Reports')
        constraints = [
            models.UniqueConstraint(
                fields=['station', 'reported_at'],
                name='weather_awos_metar_station_time_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['station', '-reported_at'], name='weather_metar_station_time_idx'),
        ]

    def __str__(self):
        return f"{self.station.code} METAR @ {self.reported_at.strftime('%Y-%m-%d %H:%M')}"


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


class OfficialForecast(models.Model):
    """A meteorologist-approved public forecast, separate from model guidance."""

    class ForecastPeriod(models.TextChoices):
        ONE_DAY = '1-day', _('1-Day Forecast')
        THREE_DAY = '3-day', _('3-Day Forecast')
        SEVEN_DAY = '7-day', _('7-Day Forecast')

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        PUBLISHED = 'published', _('Published')
        ARCHIVED = 'archived', _('Archived')

    title = models.CharField(max_length=255, verbose_name=_('Forecast Title'))
    forecast_period = models.CharField(
        max_length=10,
        choices=ForecastPeriod.choices,
        verbose_name=_('Forecast Period'),
    )
    valid_from = models.DateField(verbose_name=_('Valid From'))
    valid_to = models.DateField(verbose_name=_('Valid Until'))
    coverage = models.CharField(
        max_length=255,
        default='Timor-Leste',
        verbose_name=_('Coverage Area'),
        help_text=_('e.g. Timor-Leste, northern coast, or selected municipalities'),
    )
    summary = models.TextField(verbose_name=_('Forecast Summary'))
    notes = models.TextField(blank=True, verbose_name=_('Meteorologist Notes'))
    image = models.ImageField(
        upload_to='official_forecasts/images/',
        null=True,
        blank=True,
        verbose_name=_('Forecast Image'),
    )
    attachment = models.FileField(
        upload_to='official_forecasts/files/',
        null=True,
        blank=True,
        verbose_name=_('Supporting File'),
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_('Publication Status'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='official_forecasts_created',
        verbose_name=_('Created By'),
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='official_forecasts_published',
        verbose_name=_('Published By'),
    )
    published_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Published At'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name = _('Official Forecast')
        verbose_name_plural = _('Official Forecasts')
        constraints = [
            models.CheckConstraint(
                condition=Q(forecast_period__in=['1-day', '3-day', '7-day']),
                name='official_forecast_period_valid',
            ),
            models.CheckConstraint(
                condition=Q(status__in=['draft', 'published', 'archived']),
                name='official_forecast_status_valid',
            ),
            models.CheckConstraint(
                condition=Q(valid_to__gte=F('valid_from')),
                name='official_forecast_validity_range',
            ),
        ]
        indexes = [
            models.Index(
                fields=['status', 'forecast_period', '-valid_from'],
                name='official_forecast_public_idx',
            ),
        ]

    def __str__(self):
        return f"{self.get_forecast_period_display()}: {self.title}"

    @property
    def primary_image(self):
        """Return a cover image or the first ordered gallery image for list cards."""
        if self.image:
            return self.image
        images = getattr(self, '_prefetched_objects_cache', {}).get('images')
        first_image = images[0] if images else self.images.order_by('sort_order', 'id').first()
        return first_image.image if first_image else None


class OfficialForecastImage(models.Model):
    forecast = models.ForeignKey(
        OfficialForecast,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_('Official Forecast'),
    )
    image = models.ImageField(upload_to='official_forecasts/gallery/', verbose_name=_('Image'))
    caption = models.CharField(max_length=255, blank=True, verbose_name=_('Image Caption'))
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name=_('Display Order'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = _('Official Forecast Image')
        verbose_name_plural = _('Official Forecast Images')

    def __str__(self):
        return self.caption or self.image.name


class OfficialForecastAttachment(models.Model):
    forecast = models.ForeignKey(
        OfficialForecast,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_('Official Forecast'),
    )
    file = models.FileField(upload_to='official_forecasts/attachments/', verbose_name=_('Supporting File'))
    title = models.CharField(max_length=255, blank=True, verbose_name=_('File Title'))
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name=_('Display Order'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = _('Official Forecast Attachment')
        verbose_name_plural = _('Official Forecast Attachments')

    def __str__(self):
        return self.title or self.file.name


class EarlyWarning(models.Model):
    class Severity(models.TextChoices):
        INFO = 'info', _('Information / Advisory')
        WARNING = 'warning', _('Warning (Orange Alert)')
        DANGER = 'danger', _('Severe Hazard Alert (Red Alert)')

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
