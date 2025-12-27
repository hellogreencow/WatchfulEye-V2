# WatchfulEye Intelligence Dashboard - React Frontend

A modern, real-time geopolitical intelligence dashboard built with React, TypeScript, and Tailwind CSS.

## Features

- **Real-time Data Visualization**: Interactive charts showing sentiment analysis trends and category distributions
- **Article Feed**: Searchable feed of latest geopolitical news with sentiment indicators
- **AI Investment Briefs**: AI-generated market insights and analysis
- **Dark Mode**: Toggle between light and dark themes
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Auto-refresh**: Data updates automatically every 5 minutes

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn
- Backend API running on port 5002 (see main project README)

## Installation

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

## Running the Application

1. Make sure the backend is running:
```bash
# In the main project directory
PORT=5002 python3 web_app.py
```

2. Start the React development server:
```bash
npm start
```

The application will open at http://localhost:3000

## Environment Variables

Create a `.env` file in the frontend directory:

```env
REACT_APP_API_URL=http://localhost:5002
```

## Building for Production

```bash
npm run build
```

The build artifacts will be stored in the `build/` directory.

## Technologies Used

- **React 18**: UI framework
- **TypeScript**: Type safety
- **Tailwind CSS**: Utility-first CSS framework
- **Recharts**: Chart library
- **Framer Motion**: Animation library
- **Axios**: HTTP client
- **Lucide React**: Icon library

## Project Structure

```
frontend/
├── public/           # Static assets
├── src/
│   ├── Dashboard.tsx # Main dashboard component
│   ├── App.tsx      # App entry point
│   ├── index.css    # Global styles with Tailwind
│   └── index.tsx    # React DOM render
├── package.json     # Dependencies and scripts
└── README.md        # This file
```

## API Endpoints Used

- `GET /api/stats` - Dashboard statistics
- `GET /api/articles` - Recent articles
- `GET /api/analyses` - AI analyses
- `GET /api/search?q={query}` - Search articles

## Customization

### Theme Colors

Edit the CSS variables in `src/index.css` to customize the color scheme:

```css
:root {
  --primary: 221.2 83.2% 53.3%;
  --background: 0 0% 100%;
  /* ... other variables */
}
```

### Chart Configuration

Modify chart colors and styles in the component's `ChartContainer` config objects.

## Troubleshooting

### CORS Issues
If you encounter CORS errors, ensure the backend has CORS enabled for your frontend URL.

### API Connection Failed
- Check if the backend is running on the correct port
- Verify the `REACT_APP_API_URL` in your `.env` file
- Check network connectivity

### Build Errors
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Clear build cache: `npm run build -- --clear-cache`

## License

See the main project LICENSE file.
