import React, { useState } from 'react';
import axios from 'axios';
import './App.css'; // Asegúrate de importar el archivo CSS

const App = () => {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [topLeftPoint, setTopLeftPoint] = useState({ lat: '', lng: '' });
  const fieldSize = useState('15000'); // Seteamos el valor inicial de fieldSize a 15000
  const [imageData, setImageData] = useState('');
  const [percentages, setPercentages] = useState(null);
  const [evi] = useState(true); // EVI siempre será true y no será visible en pantalla

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post('http://localhost:8500/api/sentinel/percentage?evi=true', {
        start_date: startDate,
        end_date: endDate,
        top_left_point: [parseFloat(topLeftPoint.lng), parseFloat(topLeftPoint.lat)],
        field_size: parseInt(fieldSize)
      });
      setImageData(response.data.image);
      setPercentages(response.data.percentage_of_evi || response.data.percentage_of_ndvi);
    } catch (error) {
      console.error('Error fetching data', error);
    }
  };

  return (
    <div className="container">
      <div className="company-name" style={{  padding: '10px', marginBottom: '20px' }}>
        <h1 style={{ color: 'white' }}>Capazeta</h1>
      </div>
      {/* <h2>Vegetation Analysis</h2> */}
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
            <label>Top Left Point Latitude:</label>
            <input type="text" value={topLeftPoint.lat} onChange={(e) => setTopLeftPoint({ ...topLeftPoint, lat: e.target.value })} required />
          </div>
          <div>
            <label>Top Left Point Longitude:</label>
            <input type="text" value={topLeftPoint.lng} onChange={(e) => setTopLeftPoint({ ...topLeftPoint, lng: e.target.value })} required />
          </div>
          {/* Campo Field Size oculto */}
          <input type="hidden" value={fieldSize} />
          {/* EVI field oculto */}
          <input type="hidden" value={evi} />
          <button type="submit" className="material-button">Submit</button>
        </form>
        <div className="results">
          {percentages && (
            <div>
              <h3>Vegetation Percentages</h3>
              <p>No Vegetation: {percentages.no_vegetation}</p>
              <p>Moderate Vegetation: {percentages.moderate_vegetation}</p>
              <p>Dense Vegetation: {percentages.dense_vegetation}</p>
            </div>
          )}
        </div>
      </div>
      {imageData && (
        <div className="image-container">
          {/* <h3>Image</h3> */}
          <img src={`data:image/png;base64,${imageData}`} alt="Vegetation Analysis" />
        </div>
      )}
    </div>
  );
};

export default App;
