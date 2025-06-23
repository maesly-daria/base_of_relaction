from django.db.models import Avg
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter  # Добавляем импорт
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Booking, House, Review
from .serializers import BookingSerializer, HouseSerializer, ReviewSerializer


class HouseViewSet(viewsets.ModelViewSet):
    queryset = House.objects.all()
    serializer_class = HouseSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
    ]
    filterset_fields = {
        "price_per_night": ["gte", "lte"],
        "capacity": ["exact", "gte"],
        "is_active": ["exact"],
    }
    search_fields = ["name", "description", "location"]

    @action(detail=False, methods=["GET"])
    def top_rated(self, request):
        """Возвращает 5 коттеджей с самым высоким рейтингом."""
        houses = House.objects.annotate(
            avg_rating=Avg("review__rating")  # Используем review вместо reviews
        ).order_by("-avg_rating")[:5]
        serializer = HouseSerializer(houses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    def book(self, request, pk=None):
        """Бронирование коттеджа через API."""
        house = self.get_object()
        serializer = BookingSerializer(data=request.data, context={"house": house})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @action(detail=False, methods=["GET"])
    def cheapest(self, request):
        """Топ-5 самых дешёвых коттеджей"""
        queryset = self.get_queryset().order_by("price_per_night")[:5]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    def set_inactive(self, request, pk=None):
        """Действие для деактивации дома (POST запрос к конкретному объекту)"""
        house = self.get_object()
        house.is_active = False
        house.save()
        return Response({"status": "house set to inactive"})

    @action(detail=False, methods=["GET"])
    def inactive(self, request):
        """Получение списка неактивных домов (GET запрос без указания объекта)"""
        queryset = self.get_queryset().filter(is_active=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ["comment", "client_id__last_name"]
    filter_backends = [
        SearchFilter,
        DjangoFilterBackend,
    ]

    def get_queryset(self):
        queryset = super().get_queryset()
        if (
            self.request.query_params.get("user") == "me"
            and self.request.user.is_authenticated
        ):
            queryset = queryset.filter(client_id__user=self.request.user)
        return queryset


class HouseHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = HouseSerializer

    def get_queryset(self):
        house_id = self.kwargs["house_id"]
        return House.history.filter(id=house_id)
