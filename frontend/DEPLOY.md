# Sirius Frontend - Deploy Guide for Netlify

## Quick Deploy

### 1. Upload to GitHub

Create a new repository called `sirius-frontend` and upload the `frontend/` folder.

### 2. Deploy on Netlify

1. Go to https://app.netlify.com
2. Click "Add new site" → "Import an existing project"
3. Select your GitHub repository
4. Configure:
   - **Build command**: `npm run build`
   - **Publish directory**: `build`
   - **Environment variables**:
     - `REACT_APP_BACKEND_URL` = your backend URL (ex: https://sirius-backend.onrender.com)

5. Click "Deploy site"

---

## Configuration

### Update Backend URL

After deploying backend on Render:
1. Go to Netlify → Your site → Site settings → Environment variables
2. Add/Edit: `REACT_APP_BACKEND_URL`
3. Redeploy (clear cache if needed)

---

## Complete Setup Flow

1. **Backend** (Render)
   - Deploy `backend/`
   - Get URL: https://sirius-backend.onrender.com

2. **Frontend** (Netlify)
   - Deploy `frontend/`
   - Set `REACT_APP_BACKEND_URL` = backend URL
   - Get URL: https://sirius-frontend.netlify.app

3. **Test**
   - Open frontend URL
   - Login/Register should work!

---

## Troubleshooting

### CORS errors
- Check `REACT_APP_BACKEND_URL` is correct in Netlify
- Make sure backend allows the frontend domain

### White screen
- Check browser console for errors
- Verify `REACT_APP_BACKEND_URL` is set

### API not responding
- Check backend is deployed and running
- Verify MongoDB connection string is correct