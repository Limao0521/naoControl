import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import SidePanel from './SidePanel';


test('exposes network management in the side navigation', () => {
  const onMenuSelect = jest.fn();
  render(
    <SidePanel
      activeMenu={null}
      onMenuSelect={onMenuSelect}
      currentUI="normal"
    />
  );

  fireEvent.click(screen.getByTitle('Red'));

  expect(onMenuSelect).toHaveBeenCalledWith('network');
});


test('exposes Nemotron observability in the side navigation', () => {
  const onMenuSelect = jest.fn();
  render(
    <SidePanel
      activeMenu={null}
      onMenuSelect={onMenuSelect}
      currentUI="normal"
    />
  );

  fireEvent.click(screen.getByTitle('Nemotron'));

  expect(onMenuSelect).toHaveBeenCalledWith('nemotron');
});
