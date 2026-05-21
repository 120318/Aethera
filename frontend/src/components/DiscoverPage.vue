<template>
  <section class="ui-section w-full">
    <div
      ref="stackRef"
      :class="layoutReady ? 'opacity-100' : 'opacity-0 pointer-events-none'"
      class="ui-section w-full transition-opacity duration-150"
      :style="stackStyle"
    >
      <div class="fixed left-0 top-none invisible pointer-events-none -z-10 overflow-hidden">
        <div ref="measureCardWrapperRef" :style="measureCardWrapperStyle">
          <MediaCard ref="measureCardRef" :media="skeletonMeasureMedia" poster-width-class="w-poster-sm sm:w-poster-md" />
        </div>
      </div>

      <section
        class="flex flex-col gap-section"
        :class="isSearchHeroCentered ? 'items-center justify-center' : 'justify-center'"
        :style="searchHeroStyle"
      >
        <div class="w-full flex flex-col gap-block" :class="searchHeroBodyClass">
          <div class="ui-page-header w-full">
            <div class="flex justify-center items-center">
              <img
                src="/icons/logo.png"
                alt="Aethera"
                class="w-brand-logo max-w-full h-auto"
              />
            </div>
          </div>

          <div ref="searchBlockRef" class="w-full flex justify-center">
            <HomeSearchBox
              v-model="searchQuery"
              :placeholder="$t('discover.searchPlaceholder')"
              :loading="loading"
              @search="handleSearch"
            />
          </div>

          <div v-if="showDiscoverButtons" class="w-full flex justify-center">
            <div class="max-w-layout w-full flex flex-wrap items-center justify-center gap-item">
              <button
                class="text-body transition-colors cursor-pointer bg-transparent border-none p-none"
                :class="activeListKey === todayUpdatesKey && discoverPanelVisible ? 'text-primary' : 'text-muted hover:text-primary'"
                @click="toggleDiscoverPanel(todayUpdatesKey)"
              >
                {{ $t('discover.todayUpdates.title') }}
              </button>
              <button
                v-for="list in discoverButtons"
                :key="list.key"
                class="text-body transition-colors cursor-pointer bg-transparent border-none p-none"
                :class="activeListKey === list.key && discoverPanelVisible ? 'text-primary' : 'text-muted hover:text-primary'"
                @click="toggleDiscoverPanel(list.key)"
              >
                {{ list.title }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="showSearchResults" class="ui-section w-full">
        <section class="ui-panel p-container flex flex-col gap-item">
          <div class="flex items-center justify-between gap-item">
            <div class="flex flex-col gap-micro min-w-0">
              <h2 class="text-title font-semibold text-color break-words">{{ $t('discover.searchResults.title') }}</h2>
            </div>
            <Button
              :label="$t('discover.searchResults.clear')"
              severity="secondary"
              variant="text"
              size="small"
              class="!px-0 !py-0 !bg-transparent !border-0 !shadow-none !text-muted hover:!text-primary shrink-0"
              @click="clearSearch"
            />
          </div>

          <div v-if="loading" ref="searchLoadingGridRef" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-container">
            <MediaCardSkeleton
              v-for="i in skeletonCount"
              :key="i"
              poster-width-class="w-poster-sm sm:w-poster-md"
              :card-height="measuredMediaCardHeight"
            />
          </div>

          <div
            v-else-if="results.length > 0"
            ref="searchResultsGridRef"
            class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-container"
          >
            <MediaCard
              v-for="item in results"
              :key="getMediaCardKey(item)"
              :media="item"
              poster-width-class="w-poster-sm sm:w-poster-md"
              :to="getMediaDetailRoute(item)"
            />
          </div>

          <EmptyState v-else :border="false" :description="$t('discover.searchResults.noResults')" />
        </section>
      </section>

      <section v-if="discoverPanelVisible" ref="discoverSectionRef" class="ui-section w-full">
        <div v-if="listsLoading && !listMetas.length" class="ui-panel p-container">
          <EmptyState :border="false" :description="$t('discover.lists.loading')" />
        </div>

        <TodayUpdatesPanel v-if="showTodayUpdatesPanel" />

        <section v-else-if="activeList" class="ui-panel p-container flex flex-col gap-item">
          <div class="flex items-center justify-between gap-item">
            <div class="flex flex-col gap-micro min-w-0">
              <h2 class="text-title font-semibold text-color break-words">{{ activeList.title }}</h2>
              <p v-if="activeList.error" class="text-caption text-muted break-words">{{ activeList.error }}</p>
            </div>
            <div v-if="activeList.items.length" class="flex items-center gap-item shrink-0">
              <Button
                :label="$t('discover.pagination.previous')"
                severity="secondary"
                variant="text"
                size="small"
                class="!px-0 !py-0 !bg-transparent !border-0 !shadow-none !text-muted hover:!text-primary"
                :disabled="!activeListHasPrevPage"
                @click="prevDiscoverPage"
              />
              <Button
                :label="$t('discover.pagination.next')"
                severity="secondary"
                variant="text"
                size="small"
                class="!px-0 !py-0 !bg-transparent !border-0 !shadow-none !text-muted hover:!text-primary"
                :disabled="!activeListHasNextPage"
                @click="nextDiscoverPage"
              />
            </div>
          </div>

          <div class="flex flex-col gap-item">
            <div
              v-if="activeList.loading"
              :ref="(el) => setListGridRef(activeList.key, el)"
              class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-container"
            >
              <MediaCardSkeleton
                v-for="i in listSkeletonCount"
                :key="`${activeList.key}-loading-${i}`"
                poster-width-class="w-poster-sm sm:w-poster-md"
                :card-height="measuredMediaCardHeight"
              />
            </div>

            <template v-else>
              <div
                v-if="activeList.items.length"
                :ref="(el) => setListGridRef(activeList.key, el)"
                class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-container"
              >
                <MediaCard
                  v-for="item in activeListItems"
                  :key="getMediaCardKey(item)"
                  :media="item"
                  poster-width-class="w-poster-sm sm:w-poster-md"
                  :to="getMediaDetailRoute(item)"
                />
              </div>

              <EmptyState v-else :border="false" :description="activeList.error || $t('empty.noData')" />
            </template>
          </div>
        </section>

        <EmptyState v-else :border="false" :description="$t('discover.lists.empty')" />
      </section>
    </div>
  </section>
</template>

<script setup>
import HomeSearchBox from './common/HomeSearchBox.vue'
import MediaCard from './common/MediaCard.vue'
import MediaCardSkeleton from './common/MediaCardSkeleton.vue'
import EmptyState from './common/EmptyState.vue'
import TodayUpdatesPanel from './TodayUpdatesPanel.vue'
import Button from 'primevue/button'
import { useDiscoverPage } from '@/composables/useDiscoverPage'

const {
  stackRef,
  searchBlockRef,
  measureCardWrapperRef,
  measureCardRef,
  searchLoadingGridRef,
  searchResultsGridRef,
  discoverSectionRef,
  skeletonMeasureMedia,
  setListGridRef,
  layoutReady,
  measureCardWrapperStyle,
  stackStyle,
  searchQuery,
  loading,
  results,
  listsLoading,
  listMetas,
  discoverButtons,
  activeList,
  activeListItems,
  activeListHasPrevPage,
  activeListHasNextPage,
  discoverPanelVisible,
  activeListKey,
  todayUpdatesKey,
  showSearchResults,
  showDiscoverButtons,
  showTodayUpdatesPanel,
  isSearchHeroCentered,
  searchHeroBodyClass,
  searchHeroStyle,
  skeletonCount,
  listSkeletonCount,
  measuredMediaCardHeight,
  handleSearch,
  clearSearch,
  toggleDiscoverPanel,
  prevDiscoverPage,
  nextDiscoverPage,
  getMediaDetailRoute,
  getMediaCardKey,
} = useDiscoverPage()
</script>
