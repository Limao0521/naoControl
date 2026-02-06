import React from 'react';
import NaoController from './components/NaoController';
import './App.css';

/**
 * Componente principal de la aplicación que renderiza el NaoController.
 * Este componente sirve como la raíz de la aplicación React.
 * @returns {JSX.Element} El componente App renderizado que contiene el NaoController
 */
function App() {
  return (
    <div className="App">
      <NaoController />
    </div>
  );
}

export default App;
