import React, { useState } from 'react';
import axios from 'axios';
import './App.css'; // Asegúrate de importar el archivo CSS

const App = () => {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [polygon, setPolygon] = useState('');
  const [imageData, setImageData] = useState('');
  const [percentages, setPercentages] = useState(null);
  const [loading, setLoading] = useState(false);
  const [evi] = useState(true); // EVI siempre será true y no será visible en pantalla

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); // Set loading to true when submit is clicked
    try {
      const parsedPolygon = JSON.parse(polygon);
      const response = await axios.post('http://localhost:8500/api/sentinel/percentage?evi=true', {
        start_date: startDate,
        end_date: endDate,
        polygon: parsedPolygon
      });
      setImageData(response.data.image);
      setPercentages(response.data.percentage_of_evi || response.data.percentage_of_ndvi);
    } catch (error) {
      console.error('Error fetching data', error);
    } finally {
      setLoading(false); // Set loading to false after the request is complete
    }
  };

  const formatPercentage = (value) => {
    return value ? value.toFixed(3) : 'N/A';
  };

  return (
    <div className="container">
      <div className="company-name" style={{ padding: '10px', marginBottom: '20px' }}>
        <h1 style={{ color: 'white' }}>Capazeta</h1>
      </div>
      <div className="content">
        <form onSubmit={handleSubmit} className="form">
          <div>
            <label>Start Date:</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
          </div>
          <div>
            <label>End Date:</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
          </div>
          <div>
            <label>Polygon:</label>
            <textarea
              value={polygon}
              onChange={(e) => setPolygon(e.target.value)}
              placeholder='Enter polygon coordinates as JSON array'
              required
            />
          </div>
          {/* EVI field oculto */}
          <input type="hidden" value={evi} />
          <button type="submit" className="material-button">Submit</button>
        </form>
        <div className="results-container">
          {loading && <div className="loading">Loading...</div>}
          {imageData && !loading && (
            <div className="image-container">
              <img src={`data:image/png;base64,${imageData}`} alt="Vegetation Analysis" />
            </div>
          )}
          {percentages && !loading && (
            <div className="results">
              <h3>Vegetation Percentages</h3>
              <p>No Vegetation: {formatPercentage(percentages.no_vegetation)}</p>
              <p>Moderate Vegetation: {formatPercentage(percentages.moderate_vegetation)}</p>
              <p>Dense Vegetation: {formatPercentage(percentages.dense_vegetation)}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default App;
