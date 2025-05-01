# core/views_upload.py
import pandas as pd
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from core.models import EnergyConsumption
import hashlib
import io


class UploadExcelView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        # Check extension
        if not (file_obj.name.endswith('.xls') or file_obj.name.endswith('.xlsx')):
            return Response({"error": "File must be Excel .xls or .xlsx"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Generate hash to prevent duplicate upload
            file_bytes = file_obj.read()
            file_hash = hashlib.md5(file_bytes).hexdigest()
            file_obj.seek(0)  # Reset pointer

            # Save file temporarily (optional)
            file_path = default_storage.save(f"uploads/{file_hash}_{file_obj.name}", ContentFile(file_bytes))

            # Read file
            df = pd.read_excel(io.BytesIO(file_bytes))

            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
            elif 'datetime' in df.columns:
                df['date'] = pd.to_datetime(df['datetime'], errors='coerce').dt.date
            else:
                return Response({"error": "Missing 'date' or 'datetime' column"}, status=status.HTTP_400_BAD_REQUEST)

            if 'consumption' not in df.columns:
                return Response({"error": "Missing 'consumption' column"}, status=status.HTTP_400_BAD_REQUEST)

            df['consumption'] = pd.to_numeric(df['consumption'], errors='coerce')
            df = df.dropna(subset=['date', 'consumption'])

            # Save each row to DB
            created_count = 0
            for _, row in df.iterrows():
                EnergyConsumption.objects.get_or_create(
                    user=request.user,
                    date=row['date'],
                    defaults={"consumption_kwh": row['consumption']}
                )
                created_count += 1

            total_consumption = df['consumption'].sum()
            average_consumption = df['consumption'].mean()

            return Response({
                "status": "success",
                "message": f"{created_count} records saved",
                "total_consumption": total_consumption,
                "average_consumption": average_consumption,
                "file_hash": file_hash
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
MODEL_PATH = os.path.join(settings.BASE_DIR, "model.pkl")
ml_model = None  # TODO: Replace with trained model when available

class PredictConsumptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        צפו לפרמטרים שונים ב-POST כדי לייצר תחזית:
        """
        data = request.data
        # לדוגמה: average_daily_consumption, weekday...
        avg_consumption = float(data.get('average_daily_consumption', 0))
        weekday = int(data.get('weekday', 0))

        # מניחים שהמודל שלנו מקבל וקטור של 2 תכונות
        prediction = ml_model.predict([[avg_consumption, weekday]])
        return Response({"predicted_consumption": prediction[0]})
    

class AnomalyDetectionView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            df = pd.read_csv(file_obj)  # ייתכן שתצטרכי להשתמש ב-read_excel אם זה קובץ אקסל
            df['datetime'] = pd.to_datetime(df['datetime'])
            df['consumption'] = pd.to_numeric(df['consumption'], errors='coerce')

            df.dropna(subset=['consumption'], inplace=True)

            mean = df['consumption'].mean()
            std = df['consumption'].std()

            threshold = 2  # סטיות תקן
            anomalies = df[df['consumption'] > mean + threshold * std]

            return Response({
                "status": "success",
                "anomalies_detected": len(anomalies),
                "anomalies": anomalies[['datetime', 'consumption']].head(10).to_dict(orient='records')
            })

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AnomalyDetectionView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            df = pd.read_csv(file_obj)

            # המרה לזמן
            df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
            df['consumption'] = pd.to_numeric(df['consumption'], errors='coerce')

            # הסרת ערכים חסרים
            df = df.dropna(subset=['datetime', 'consumption'])

            # חישוב ממוצע וסטיית תקן
            mean = df['consumption'].mean()
            std = df['consumption'].std()

            # סינון אנומליות
            df['is_anomaly'] = ((df['consumption'] > mean + 2*std) | (df['consumption'] < mean - 2*std))
            anomalies = df[df['is_anomaly']]

            return Response({
                "status": "success",
                "anomalies_found": int(anomalies.shape[0]),
                "sample_anomalies": anomalies[['datetime', 'consumption']].head(10).to_dict(orient="records")
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
