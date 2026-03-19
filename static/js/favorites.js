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
            throw new Error('Toggle failed');
        }
        return response.json();
    })
    .then(function(data) {
        // Update sidebar favorites list dynamically
        updateSidebarFavorites();
    })
    .catch(function(err) {
        // Revert on failure
        icon.classList.toggle('favorited');
        icon.classList.toggle('fas');
        icon.classList.toggle('far');
        btn.title = wasFavorited ? 'Remove from favorites' : 'Add to favorites';
        console.error('Favorite toggle error:', err);
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
