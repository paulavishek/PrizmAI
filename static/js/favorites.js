/**
 * PrizmAI — My Favorites toggle
 * Handles heart button clicks to add/remove favorites via API.
 */
function toggleFavorite(btn) {
    var icon = btn.querySelector('.favorite-heart');
    var favoriteType = btn.getAttribute('data-favorite-type');
    var objectId = parseInt(btn.getAttribute('data-object-id'), 10);

    if (!favoriteType || !objectId) return;

    // Optimistic UI update
    var wasFavorited = icon.classList.contains('favorited');
    icon.classList.toggle('favorited');
    icon.classList.toggle('fas');
    icon.classList.toggle('far');
    btn.title = wasFavorited ? 'Add to favorites' : 'Remove from favorites';

    // Get CSRF token
    var csrfToken = '';
    var csrfMeta = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfMeta) {
        csrfToken = csrfMeta.value;
    } else {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i].trim();
            if (c.indexOf('csrftoken=') === 0) {
                csrfToken = c.substring('csrftoken='.length);
                break;
            }
        }
    }

    fetch('/api/favorites/toggle/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
            favorite_type: favoriteType,
            object_id: objectId,
        }),
    })
    .then(function(response) {
        if (!response.ok) {
            // Revert optimistic update on failure
            icon.classList.toggle('favorited');
            icon.classList.toggle('fas');
            icon.classList.toggle('far');
            btn.title = wasFavorited ? 'Remove from favorites' : 'Add to favorites';
            return response.json().then(function(errData) {
                _showFavToast(errData.error || 'Could not update favorite. Please try again.');
            }).catch(function() {
                _showFavToast('Could not update favorite. Please try again.');
            });
        }
        return response.json().then(function(data) {
            // Update sidebar favorites list dynamically
            updateSidebarFavorites();
        });
    })
    .catch(function(err) {
        // Revert on network failure
        icon.classList.toggle('favorited');
        icon.classList.toggle('fas');
        icon.classList.toggle('far');
        btn.title = wasFavorited ? 'Remove from favorites' : 'Add to favorites';
        console.error('Favorite toggle error:', err);
        _showFavToast('Could not update favorite. Please check your connection.');
    });
}


/**
 * Fetch updated favorites and re-render the sidebar list.
 */
function updateSidebarFavorites() {
    var container = document.getElementById('sidebarFavoritesList');
    var emptyHint = document.getElementById('sidebarFavoritesEmpty');
    if (!container) return;

    fetch('/api/favorites/list/')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var favs = data.favorites || [];
            container.innerHTML = '';

            if (favs.length === 0) {
                if (emptyHint) emptyHint.style.display = '';
                return;
            }
            if (emptyHint) emptyHint.style.display = 'none';

            favs.forEach(function(fav) {
                var li = document.createElement('li');
                li.className = 'sidebar-nav-item sidebar-fav-item';
                var a = document.createElement('a');
                a.href = fav.url;
                a.className = 'sidebar-nav-link sidebar-fav-link';
                a.title = fav.display_name;
                a.innerHTML = '<i class="' + escapeHtml(fav.icon_class) + ' sidebar-nav-icon sidebar-fav-icon"></i>' +
                    '<span class="sidebar-label sidebar-fav-name">' + escapeHtml(fav.display_name) + '</span>';
                li.appendChild(a);
                container.appendChild(li);
            });
        })
        .catch(function(err) {
            console.error('Failed to refresh favorites:', err);
        });
}

function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

/**
 * Show a brief inline toast/snackbar for favorites errors.
 */
function _showFavToast(message) {
    var existing = document.getElementById('fav-toast');
    if (existing) existing.remove();
    var toast = document.createElement('div');
    toast.id = 'fav-toast';
    toast.style.cssText = [
        'position:fixed', 'bottom:24px', 'left:50%', 'transform:translateX(-50%)',
        'background:#1e293b', 'color:#f1f5f9', 'padding:10px 20px',
        'border-radius:8px', 'font-size:0.875rem', 'z-index:9999',
        'box-shadow:0 4px 16px rgba(0,0,0,0.3)', 'pointer-events:none',
        'transition:opacity 0.3s',
    ].join(';');
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(function() {
        toast.style.opacity = '0';
        setTimeout(function() { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 400);
    }, 3500);
}
