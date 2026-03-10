import React from "react";
import { PieChart, Pie, Cell, Tooltip, Legend } from "recharts";
import data from "../data/pluginsAggregated.json";

const DeprecatedApisChart = () => {
  const deprecatedCount = data.filter(d => d.deprecated_apis_used).length;
  const safeCount = data.length - deprecatedCount;

  const chartData = [
    { name: "Uses Deprecated APIs", value: deprecatedCount },
    { name: "Safe Plugins", value: safeCount }
  ];

  const COLORS = ["#FF4C4C", "#4CAF50"];

  return (
    <div style={{ width: "100%", maxWidth: 500, margin: "0 auto" }}>
      <h2>Plugins with Deprecated APIs</h2>
      <PieChart width={400} height={400}>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          outerRadius={120}
          dataKey="value"
          label
        >
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </div>
  );
};

export default DeprecatedApisChart;