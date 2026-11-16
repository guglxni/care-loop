import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { bpReadings, glucoseReadings } from "@/data/demo";
import { BloodPressureChart } from "@/pages/blood-pressure/BloodPressureChart";
import { GlucoseChart } from "@/pages/glucose/GlucoseChart";

export function TrendCharts() {
  return (
    <div className="grid min-w-0 gap-4 lg:grid-cols-2">
      <Card className="min-w-0">
        <CardHeader>
          <CardTitle>Glucose</CardTitle>
          <CardDescription>One line for each source, in mg/dL.</CardDescription>
        </CardHeader>
        <CardContent>
          <GlucoseChart readings={glucoseReadings} />
        </CardContent>
      </Card>
      <Card className="min-w-0">
        <CardHeader>
          <CardTitle>Blood pressure</CardTitle>
          <CardDescription>Systolic and diastolic, in mmHg.</CardDescription>
        </CardHeader>
        <CardContent>
          <BloodPressureChart readings={bpReadings} />
        </CardContent>
      </Card>
    </div>
  );
}

export default TrendCharts;
